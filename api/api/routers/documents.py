import uuid
from datetime import datetime, timezone
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, status
from pydantic import BaseModel

from api.infrastructure.queue import get_queue_service
from api.services.db import db
from auth.dependencies.current_user import get_current_user
from shared_queue import (
    QueueService,
    DocumentStatus,
    StorageService,
    EmbeddingService,
    VectorStore,
    LLMService,
)

# Initialize APIRouter
router = APIRouter(tags=["Documents & Search"])


class SearchRequest(BaseModel):
    query: str
    workspace_id: Optional[str] = None


@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    queue: Annotated[QueueService, Depends(get_queue_service)],
    current_user: Annotated[dict, Depends(get_current_user)],
    file: Annotated[UploadFile, File(...)],
    workspace_id: Annotated[str, Form(alias="workspaceId")],
):
    """
    Async Ingestion API for uploading documents.
    Accepts raw multipart file and workspace ID, authenticates via Bearer JWT,
    extracts user_id from the token, saves metadata to MongoDB under 'QUEUED' status,
    and publishes an ingestion event to the Redis Stream to begin async stages.
    """
    filename = file.filename
    if not filename.endswith((".pdf", ".txt", ".md", ".docx", ".json")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Supported: .pdf, .txt, .md, .docx, .json",
        )

    # Extract user_id securely from the JWT token payload
    user_id = current_user["sub"]

    # 1. Generate unique Document ID
    document_id = str(uuid.uuid4())

    # 2. Upload file to S3/MinIO (falls back to local filesystem inside StorageService if needed)
    try:
        file_bytes = await file.read()
        s3_key = f"workspaces/{workspace_id}/docs/{document_id}_{filename}"
        storage_service = StorageService()
        storage_path = await storage_service.upload(file_bytes, filename, s3_key)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document to storage: {str(e)}",
        )

    # 3. Create document record in MongoDB documents collection
    now = datetime.now(timezone.utc).isoformat()
    document_record = {
        "_id": document_id,
        "filename": filename,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "status": DocumentStatus.QUEUED.value,
        "storage_path": storage_path,
        "created_at": now,
        "updated_at": now,
    }

    try:
        await db["documents"].insert_one(document_record)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record document metadata in database: {str(e)}",
        )

    # 4. Trigger Async parsing by publishing to redis stream 'document:parse'
    try:
        # Step 3 Consumer Groups setup helper
        await queue.create_consumer_group("document:parse", "parse-group")
        await queue.create_consumer_group("document:chunk", "chunk-group")
        await queue.create_consumer_group("document:embed", "embed-group")

        # Publish parse task payload
        await queue.publish(
            "document:parse",
            {"document_id": document_id, "attempt": 1},
        )
        print(f"[API] Ingestion task scheduled for document '{document_id}' successfully.")
    except Exception as e:
        print(f"Warning: failed to enqueue async ingestion task: {e}")

    return {
        "document_id": document_id,
        "filename": filename,
        "user_id": user_id,
        "workspace_id": workspace_id,
        "status": DocumentStatus.QUEUED.value,
        "storage_path": storage_path,
    }


@router.get("/documents/{id}")
async def get_document_status(
    id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Get the ingestion status of a specific document.
    Requires authentication via token to protect document records.
    """
    doc = await db["documents"].find_one({"_id": id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{id}' not found.",
        )

    # Optional: verify user possesses permission for this document
    user_id = current_user["sub"]
    if doc.get("user_id") != user_id and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this document record.",
        )

    return {
        "document_id": doc["_id"],
        "filename": doc["filename"],
        "user_id": doc.get("user_id"),
        "workspace_id": doc.get("workspace_id"),
        "status": doc["status"],
        "storage_path": doc["storage_path"],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@router.post("/search")
async def search_documents(
    request: SearchRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Semantic Search & RAG Generation API.
    Embeds user query, retrieves candidate documents from Vector DB,
    and runs contextual legal synthesis. Requires authentication.
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty.",
        )

    # 1. Embed query
    embedding_service = EmbeddingService()
    query_vector = embedding_service.embed(request.query)

    # 2. Search closest matches in VectorDB
    vector_store = VectorStore()
    vector_store.set_mongo_db(db)
    await vector_store.init_collection()

    results = await vector_store.search(query_vector, limit=5)

    # 3. Filter by workspace_id if provided
    if request.workspace_id:
        results = [
            r
            for r in results
            if r["payload"].get("workspace_id") == request.workspace_id
        ]

    # 4. Build context
    context_chunks = [r["payload"].get("text", "") for r in results]

    # 5. Synthesize answer
    llm_service = LLMService()
    answer = await llm_service.generate(context_chunks, request.query)

    return {
        "query": request.query,
        "answer": answer,
        "results": [
            {
                "id": r["id"],
                "score": r["score"],
                "payload": {
                    "text": r["payload"].get("text"),
                    "page_number": r["payload"].get("metadata", {}).get("page_number"),
                    "workspace_id": r["payload"].get("workspace_id"),
                    "document_id": r["payload"].get("document_id"),
                },
            }
            for r in results
        ],
    }
