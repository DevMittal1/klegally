import os
import sys
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

# Add shared paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"),
)

from shared_queue import DocumentStatus
from worker.ingestion import DocumentIngestionPipeline

# In-memory simulated DB
MOCK_DOCUMENTS_DB = {}


class MockCollection:
    def __init__(self, name):
        self.name = name

    async def find_one(self, query):
        if self.name == "documents":
            doc_id = query.get("_id")
            return MOCK_DOCUMENTS_DB.get(doc_id)
        return None

    async def update_one(self, query, update, upsert=False):
        if self.name == "documents":
            doc_id = query.get("_id")
            if doc_id in MOCK_DOCUMENTS_DB:
                MOCK_DOCUMENTS_DB[doc_id].update(update.get("$set", {}))
        return AsyncMock()


# Mock DB mapping
mock_db = MagicMock()
mock_db.__getitem__.side_effect = lambda name: MockCollection(name)


async def test_premature_extraction_handling():
    print("Testing premature extraction handling...")

    # Seed mock document ID pointing to a non-existent path in storage
    document_id = "doc_incomplete_upload_99"
    non_existent_s3_path = "s3://mock-bucket/missing_file.pdf"

    MOCK_DOCUMENTS_DB[document_id] = {
        "_id": document_id,
        "filename": "missing_file.pdf",
        "user_id": "user_worker_01",
        "workspace_id": "workspace_worker_01",
        "status": DocumentStatus.QUEUED.value,
        "storage_path": non_existent_s3_path,
    }

    mock_queue = AsyncMock()

    # Instatiate Pipeline
    pipeline = DocumentIngestionPipeline(
        db=mock_db,
        queue=mock_queue,
        storage_settings={"S3_BUCKET": "mock-bucket"},
    )

    # Invoke parse_document on a non-existent file, expecting FileNotFoundError
    print("Attempting to parse non-existent S3/storage path...")
    try:
        await pipeline.parse_document(document_id)
        assert False, "Expected FileNotFoundError but parsing succeeded!"
    except FileNotFoundError as err:
        print(f"Caught expected FileNotFoundError: '{err}'")

    # Assert document status did NOT advance to PARSED
    assert MOCK_DOCUMENTS_DB[document_id]["status"] == DocumentStatus.PARSING.value
    print("Verification successful! Document parsing safely blocked until file arrives.")


if __name__ == "__main__":
    asyncio.run(test_premature_extraction_handling())
