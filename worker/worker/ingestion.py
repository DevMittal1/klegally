import uuid
from typing import Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from shared_queue import (
    QueueService,
    DocumentStatus,
    EmbeddingStatus,
    StorageService,
    LiteParseService,
    ChunkService,
    EmbeddingService,
    VectorStore,
    FailedEvent,
)


class DocumentIngestionPipeline:
    def __init__(self, db: AsyncIOMotorDatabase, queue: QueueService, storage_settings: dict):
        self.db = db
        self.queue = queue

        # Initialize services using the shared queue module implementations
        self.storage_service = StorageService(
            bucket=storage_settings.get("S3_BUCKET", "klegally-documents"),
            endpoint_url=storage_settings.get("S3_ENDPOINT_URL"),
            access_key=storage_settings.get("AWS_ACCESS_KEY_ID"),
            secret_key=storage_settings.get("AWS_SECRET_ACCESS_KEY"),
            region=storage_settings.get("AWS_REGION", "us-east-1"),
        )
        self.parse_service = LiteParseService()
        self.chunk_service = ChunkService()
        self.embedding_service = EmbeddingService()

        self.vector_store = VectorStore()
        self.vector_store.set_mongo_db(db)

    async def parse_document(self, document_id: str) -> None:
        """
        Step 5 Worker Action:
        Downloads the document from storage, parses pages using LiteParse,
        saves pages in parsed_pages collection, and triggers the chunking stage.
        """
        print(f"[Parse Worker] Starting parsing for document '{document_id}'...")

        # 1. Update status to PARSING
        await self.db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.PARSING.value}},
        )

        # 2. Retrieve document metadata
        document = await self.db["documents"].find_one({"_id": document_id})
        if not document:
            raise ValueError(f"Document '{document_id}' not found in database.")

        storage_path = document["storage_path"]

        # 3. Check if document is actually present in storage yet (prevents premature extraction)
        if not await self.storage_service.exists(storage_path):
            raise FileNotFoundError(
                f"Ingestion S3 file '{storage_path}' is not fully written/present yet. "
                "Text extraction cannot proceed. Retrying in background..."
            )

        # 4. Download the file to local temporary storage
        local_file = await self.storage_service.download(storage_path)

        # 4. Parse document using LiteParseService
        result = self.parse_service.parse(local_file)

        # 5. Insert parsed pages into MongoDB
        # Clear any existing pages if this is a retry to avoid duplicates
        await self.db["parsed_pages"].delete_many({"document_id": document_id})

        for page in result.pages:
            parsed_page_doc = {
                "document_id": document_id,
                "page_number": page.number,
                "content": page.content,
            }
            await self.db["parsed_pages"].insert_one(parsed_page_doc)

        # 6. Update document status to PARSED
        await self.db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.PARSED.value}},
        )
        print(f"[Parse Worker] Document '{document_id}' successfully parsed into {len(result.pages)} pages.")

        # 7. Queue chunking stage via Redis Stream 'document:chunk'
        await self.queue.publish(
            "document:chunk",
            {"document_id": document_id, "attempt": 1},
        )

    async def chunk_document(self, document_id: str) -> None:
        """
        Step 6 Worker Action:
        Retrieves parsed pages from MongoDB, sections them into chunks using ChunkService,
        saves chunks in chunks collection under PENDING status, and triggers the embedding stage.
        """
        print(f"[Chunk Worker] Starting chunking for document '{document_id}'...")

        # 1. Update status to CHUNKING
        await self.db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.CHUNKING.value}},
        )

        # 2. Retrieve all parsed pages for the document
        cursor = self.db["parsed_pages"].find({"document_id": document_id})
        pages = []
        async for doc in cursor:
            pages.append(doc)

        if not pages:
            raise ValueError(f"No parsed pages found for document '{document_id}'.")

        # 3. Process chunking using ChunkService
        chunks = self.chunk_service.create_chunks(pages)

        # 4. Insert chunks into MongoDB chunks collection
        # Clear existing chunks if this is a retry
        await self.db["chunks"].delete_many({"document_id": document_id})

        for idx, chunk in enumerate(chunks):
            chunk_doc = {
                "document_id": document_id,
                "chunk_index": idx,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "embedding_status": EmbeddingStatus.PENDING.value,
            }
            await self.db["chunks"].insert_one(chunk_doc)

        # 5. Update document status to CHUNKED
        await self.db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.CHUNKED.value}},
        )
        print(f"[Chunk Worker] Document '{document_id}' successfully split into {len(chunks)} chunks.")

        # 6. Queue embedding stage via Redis Stream 'document:embed'
        await self.queue.publish(
            "document:embed",
            {"document_id": document_id, "attempt": 1},
        )

    async def embed_document(self, document_id: str) -> None:
        """
        Step 7 Worker Action:
        Retrieves PENDING chunks, generates vector embeddings, upserts into the
        Vector Store (Qdrant / persistent Mongo fallback), and sets document to EMBEDDED.
        """
        print(f"[Embedding Worker] Starting embedding for document '{document_id}'...")

        # 1. Update status to EMBEDDING
        await self.db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.EMBEDDING.value}},
        )

        # 2. Retrieve workspace_id from document for query segmentation
        document = await self.db["documents"].find_one({"_id": document_id})
        if not document:
            raise ValueError(f"Document '{document_id}' not found.")
        workspace_id = document.get("workspace_id")

        # 3. Retrieve all PENDING chunks for this document
        cursor = self.db["chunks"].find(
            {
                "document_id": document_id,
                "embedding_status": EmbeddingStatus.PENDING.value,
            }
        )
        chunks = []
        async for doc in cursor:
            chunks.append(doc)

        if not chunks:
            print(f"[Embedding Worker] No pending chunks found for document '{document_id}'. Marking EMBEDDED.")
            await self.db["documents"].update_one(
                {"_id": document_id},
                {"$set": {"status": DocumentStatus.EMBEDDED.value}},
            )
            return

        # 4. Initialize Vector Collection
        await self.vector_store.init_collection()

        # 5. Embed and upsert each chunk
        for chunk in chunks:
            chunk_id = str(chunk["_id"])
            chunk_text = chunk["text"]

            # Compute vector using EmbeddingService
            vector = self.embedding_service.embed(chunk_text)

            # Upsert into VectorStore
            payload = {
                "document_id": document_id,
                "workspace_id": workspace_id,
                "text": chunk_text,
                "metadata": chunk.get("metadata", {}),
            }
            await self.vector_store.upsert(chunk_id, vector, payload)

            # Update chunk status to COMPLETED
            await self.db["chunks"].update_one(
                {"_id": chunk["_id"]},
                {"$set": {"embedding_status": EmbeddingStatus.COMPLETED.value}},
            )

        # 6. Update document status to EMBEDDED
        await self.db["documents"].update_one(
            {"_id": document_id},
            {"$set": {"status": DocumentStatus.EMBEDDED.value}},
        )
        print(f"[Embedding Worker] Document '{document_id}' successfully indexed and embedded!")
