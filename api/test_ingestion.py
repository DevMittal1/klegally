import os
import sys
from unittest.mock import patch, AsyncMock

# Add directories to system path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/auth"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../shared/queue"))

# Mock Database Store
MOCK_DOCUMENTS_DB = {}
MOCK_PARSED_PAGES_DB = []
MOCK_CHUNKS_DB = []
MOCK_QDRANT_SIMULATION = []


class MockCollection:
    def __init__(self, name):
        self.name = name

    async def insert_one(self, document):
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
        # Return a mock async cursor
        results = []
        if self.name == "qdrant_simulation":
            results = MOCK_QDRANT_SIMULATION
        elif self.name == "parsed_pages":
            doc_id = query.get("document_id")
            results = [p for p in MOCK_PARSED_PAGES_DB if p["document_id"] == doc_id]

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
        return AsyncMock()

    async def delete_many(self, query):
        return AsyncMock()


# Inject mock db mapping
def mock_db_getitem(name):
    return MockCollection(name)


# Global patches
patcher_db = patch("api.services.db.db")
mock_db = patcher_db.start()
mock_db.__getitem__.side_effect = mock_db_getitem

from api.app import app
from api.infrastructure.queue import get_queue_service
from auth.dependencies.current_user import get_current_user
from fastapi.testclient import TestClient

# Mock Queue dependencies
mock_queue = AsyncMock()
app.dependency_overrides[get_queue_service] = lambda: mock_queue

# Mock Auth context dependency to return authenticated claims
mock_current_user = {
    "sub": "user_admin_01",
    "sid": "5f8e695a-a6a6-4124-bb11-e27b47af3b82",
    "org_id": "org_klegally",
    "role": "admin",
    "type": "access",
}
app.dependency_overrides[get_current_user] = lambda: mock_current_user

client = TestClient(app)


def test_document_ingestion_api_flow():
    print("Testing document upload API endpoint with secure auth context...")
    mock_queue.reset_mock()

    # 1. Post document upload (userId form param removed - resolved from token mock!)
    response = client.post(
        "/documents/upload",
        data={"workspaceId": "workspace_test_01"},
        files={"file": ("report.txt", b"CONFIDENTIAL LEGAL SERVICES AGREEMENT\n\nPage 1 text content here.", "text/plain")},
    )

    assert response.status_code == 201
    data = response.json()
    assert "document_id" in data
    assert data["filename"] == "report.txt"
    assert data["user_id"] == "user_admin_01"  # Derived from sub claim of JWT token!
    assert data["workspace_id"] == "workspace_test_01"
    assert data["status"] == "QUEUED"

    doc_id = data["document_id"]

    # Verify storage upload registered locally/in-memory mock
    assert doc_id in MOCK_DOCUMENTS_DB
    assert MOCK_DOCUMENTS_DB[doc_id]["status"] == "QUEUED"

    # Verify queue service was triggered to schedule ingestion
    mock_queue.publish.assert_called_once()
    topic, payload = mock_queue.publish.call_args[0]
    assert topic == "document:parse"
    assert payload["document_id"] == doc_id
    print("Upload API flow validated successfully!")

    # 2. Test status check endpoint
    print("Testing status check API...")
    response = client.get(f"/documents/{doc_id}")
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["document_id"] == doc_id
    assert status_data["status"] == "QUEUED"
    print("Status API validated successfully!")

    # 3. Test semantic search endpoint
    print("Testing semantic search and RAG API...")

    # Seed mock Qdrant collection fallback DB with a chunk of legal text
    MOCK_QDRANT_SIMULATION.append(
        {
            "_id": "chunk_01",
            "vector": [0.1] * 384,  # Deterministic test vector
            "payload": {
                "document_id": doc_id,
                "workspace_id": "workspace_test_01",
                "text": "CONFIDENTIAL LEGAL SERVICES AGREEMENT Section 1.1: Scope of Work.",
                "metadata": {"page_number": 1},
            },
        }
    )

    # Perform a search request
    response = client.post(
        "/search",
        json={"query": "What is the scope of work?", "workspace_id": "workspace_test_01"},
    )

    assert response.status_code == 200
    search_res = response.json()
    assert search_res["query"] == "What is the scope of work?"
    assert "answer" in search_res
    assert len(search_res["results"]) > 0
    assert search_res["results"][0]["payload"]["workspace_id"] == "workspace_test_01"
    assert "CONFIDENTIAL LEGAL SERVICES" in search_res["results"][0]["payload"]["text"]
    print("Search RAG API validated successfully!")


if __name__ == "__main__":
    try:
        test_document_ingestion_api_flow()
        print("All document ingestion integration tests passed successfully!")
    finally:
        patcher_db.stop()
