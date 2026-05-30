import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Add shared paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"))

from shared_queue import DocumentStatus, EmbeddingStatus, StorageService

# In-memory simulated DB
MOCK_DOCUMENTS_DB = {}
MOCK_PARSED_PAGES_DB = []
MOCK_CHUNKS_DB = []
MOCK_QDRANT_SIMULATION = []


class MockCollection:
    def __init__(self, name):
        self.name = name

    async def insert_one(self, document):
        import uuid
        if "_id" not in document:
            document["_id"] = str(uuid.uuid4())
        if self.name == "documents":
            doc_id = document["_id"]
            MOCK_DOCUMENTS_DB[doc_id] = document
        elif self.name == "parsed_pages":
            MOCK_PARSED_PAGES_DB.append(document)
        elif self.name == "chunks":
            MOCK_CHUNKS_DB.append(document)
        elif self.name == "qdrant_simulation":
            MOCK_QDRANT_SIMULATION.append(document)
        return AsyncMock()

    async def find_one(self, query):
        if self.name == "documents":
            doc_id = query.get("_id")
            return MOCK_DOCUMENTS_DB.get(doc_id)
        return None

    def find(self, query):
        results = []
        if self.name == "parsed_pages":
            doc_id = query.get("document_id")
            results = [p for p in MOCK_PARSED_PAGES_DB if p["document_id"] == doc_id]
        elif self.name == "chunks":
            doc_id = query.get("document_id")
            results = [c for c in MOCK_CHUNKS_DB if c["document_id"] == doc_id]
        elif self.name == "qdrant_simulation":
            results = MOCK_QDRANT_SIMULATION

        class AsyncCursor:
            def __init__(self, items):
                self.items = items
                self.index = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self.index >= len(self.items):
                    raise StopAsyncIteration
                val = self.items[self.index]
                self.index += 1
                return val

        return AsyncCursor(results)

    async def update_one(self, query, update, upsert=False):
        if self.name == "documents":
            doc_id = query.get("_id")
            if doc_id in MOCK_DOCUMENTS_DB:
                MOCK_DOCUMENTS_DB[doc_id].update(update.get("$set", {}))
        elif self.name == "chunks":
            # Simple chunk field updating
            chunk_id = query.get("_id")
            for c in MOCK_CHUNKS_DB:
                if c.get("_id") == chunk_id:
                    c.update(update.get("$set", {}))
        elif self.name == "qdrant_simulation":
            doc_id = query.get("_id")
            found = False
            for c in MOCK_QDRANT_SIMULATION:
                if c["_id"] == doc_id:
                    c.update(update.get("$set", {}))
                    found = True
                    break
            if not found and upsert:
                new_doc = {"_id": doc_id}
                new_doc.update(update.get("$set", {}))
                MOCK_QDRANT_SIMULATION.append(new_doc)
        return AsyncMock()

    async def delete_many(self, query):
        if self.name == "parsed_pages":
            doc_id = query.get("document_id")
            global MOCK_PARSED_PAGES_DB
            MOCK_PARSED_PAGES_DB = [p for p in MOCK_PARSED_PAGES_DB if p["document_id"] != doc_id]
        elif self.name == "chunks":
            doc_id = query.get("document_id")
            global MOCK_CHUNKS_DB
            MOCK_CHUNKS_DB = [c for c in MOCK_CHUNKS_DB if c["document_id"] != doc_id]
        return AsyncMock()


# Mock DB mappings
mock_db = MagicMock()
mock_db.__getitem__.side_effect = lambda name: MockCollection(name)

from worker.ingestion import DocumentIngestionPipeline


async def test_worker_ingestion_pipeline():
    print("Testing Background Worker Ingestion Pipeline stages...")

    # Initialize mocked services
    mock_queue = AsyncMock()

    # Seed mock Storage file path
    document_id = "doc_test_uuid_99"
    local_temp_file_dir = os.path.dirname(os.path.abspath(__file__))
    dummy_filepath = os.path.join(local_temp_file_dir, "dummy_contract.txt")

    # Write dummy document
    with open(dummy_filepath, "w") as f:
        f.write(
            "CONFIDENTIAL LEGAL SERVICES AGREEMENT\n\n"
            "Section 1.1: Scope of Work.\n"
            "This covers document chunking workflows."
        )

    # Register document record in MongoDB
    MOCK_DOCUMENTS_DB[document_id] = {
        "_id": document_id,
        "filename": "dummy_contract.txt",
        "user_id": "user_worker_01",
        "workspace_id": "workspace_worker_01",
        "status": DocumentStatus.QUEUED.value,
        "storage_path": dummy_filepath,
    }

    # Instatiate Pipeline
    pipeline = DocumentIngestionPipeline(
        db=mock_db,
        queue=mock_queue,
        storage_settings={"S3_BUCKET": "mock-bucket"},
    )

    # 1. Execute Parsing Stage (Step 5)
    print("Stage 1: Parsing...")
    await pipeline.parse_document(document_id)

    # Verify transition status is PARSED
    assert MOCK_DOCUMENTS_DB[document_id]["status"] == DocumentStatus.PARSED.value
    # Verify parsed_pages in MongoDB
    assert len(MOCK_PARSED_PAGES_DB) == 2
    assert MOCK_PARSED_PAGES_DB[0]["page_number"] == 1
    assert "Scope of Work" in MOCK_PARSED_PAGES_DB[1]["content"]["text"]

    # Verify task queued to next stage 'document:chunk'
    mock_queue.publish.assert_called_with(
        "document:chunk", {"document_id": document_id, "attempt": 1}
    )
    print("Parsing stage completed successfully!")

    # 2. Execute Chunking Stage (Step 6)
    print("Stage 2: Chunking...")
    mock_queue.reset_mock()
    await pipeline.chunk_document(document_id)

    # Verify transition status is CHUNKED
    assert MOCK_DOCUMENTS_DB[document_id]["status"] == DocumentStatus.CHUNKED.value
    # Verify chunks recorded in MongoDB
    assert len(MOCK_CHUNKS_DB) == 2
    assert MOCK_CHUNKS_DB[0]["chunk_index"] == 0
    assert MOCK_CHUNKS_DB[0]["embedding_status"] == EmbeddingStatus.PENDING.value

    # Verify task queued to next stage 'document:embed'
    mock_queue.publish.assert_called_with(
        "document:embed", {"document_id": document_id, "attempt": 1}
    )
    print("Chunking stage completed successfully!")

    # 3. Execute Embedding Stage (Step 7)
    print("Stage 3: Embedding...")
    mock_queue.reset_mock()
    await pipeline.embed_document(document_id)

    # Verify final transition status is EMBEDDED
    assert MOCK_DOCUMENTS_DB[document_id]["status"] == DocumentStatus.EMBEDDED.value
    # Verify that all chunks were completed
    for c in MOCK_CHUNKS_DB:
        assert c["embedding_status"] == EmbeddingStatus.COMPLETED.value

    # Verify vector store upsertion (high-fidelity persistent mongo simulation)
    assert len(MOCK_QDRANT_SIMULATION) > 0
    assert MOCK_QDRANT_SIMULATION[0]["payload"]["document_id"] == document_id
    assert MOCK_QDRANT_SIMULATION[0]["payload"]["workspace_id"] == "workspace_worker_01"
    print("Embedding stage completed successfully!")

    # Cleanup temporary local test file
    if os.path.exists(dummy_filepath):
        os.remove(dummy_filepath)
    print("Cleanup completed.")


if __name__ == "__main__":
    from unittest.mock import MagicMock
    asyncio.run(test_worker_ingestion_pipeline())
    print("All ingestion worker stage tests passed successfully!")
