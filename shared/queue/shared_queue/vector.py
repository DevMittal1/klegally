import os
import httpx
from typing import List, Dict, Any, Optional


class VectorStore:
    def __init__(self, collection_name: str = "klegally_chunks"):
        self.collection_name = collection_name
        self.qdrant_url = os.environ.get("QDRANT_URL", None)
        self.qdrant_api_key = os.environ.get("QDRANT_API_KEY", None)
        self.mongo_collection = None

    def set_mongo_db(self, db):
        """Allows injecting the motor db object for fallback persistent simulation."""
        if db is not None:
            self.mongo_collection = db["qdrant_simulation"]

    async def init_collection(self) -> None:
        """Initializes collection in Qdrant if real, or logs simulation status."""
        if self.qdrant_url:
            headers = {}
            if self.qdrant_api_key:
                headers["api-key"] = self.qdrant_api_key
            try:
                # Clean URL string to avoid slash duplication
                url = self.qdrant_url.rstrip("/")
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(
                        f"{url}/collections/{self.collection_name}",
                        headers=headers,
                    )
                    if resp.status_code != 200:
                        await client.put(
                            f"{url}/collections/{self.collection_name}",
                            headers=headers,
                            json={
                                "vectors": {
                                    "size": 384,
                                    "distance": "Cosine",
                                }
                            },
                        )
                        print(f"[Qdrant] Created collection '{self.collection_name}'.")
                    else:
                        print(f"[Qdrant] Collection '{self.collection_name}' already exists.")
                    return
            except Exception as e:
                print(f"[Qdrant] Connection failed: {e}. Activating MongoDB vector simulation fallback.")
        else:
            print("[Qdrant] URL not configured. Activating MongoDB vector simulation fallback.")

    async def upsert(self, id: str, vector: List[float], payload: Dict[str, Any]) -> None:
        """
        Upserts a point to Qdrant or falls back to MongoDB simulation.
        """
        if self.qdrant_url:
            headers = {}
            if self.qdrant_api_key:
                headers["api-key"] = self.qdrant_api_key
            try:
                url = self.qdrant_url.rstrip("/")
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.put(
                        f"{url}/collections/{self.collection_name}/points",
                        headers=headers,
                        json={
                            "points": [
                                {
                                    "id": id,
                                    "vector": vector,
                                    "payload": payload,
                                }
                            ]
                        },
                    )
                    if resp.status_code == 200:
                        print(f"[Qdrant] Upserted point '{id}' to Qdrant.")
                        return
            except Exception as e:
                print(f"[Qdrant] Failed upsert to Qdrant: {e}. Falling back to MongoDB.")

        # MongoDB simulation fallback
        if self.mongo_collection is not None:
            try:
                await self.mongo_collection.update_one(
                    {"_id": id},
                    {"$set": {"_id": id, "vector": vector, "payload": payload}},
                    upsert=True,
                )
                print(f"[VectorDB Mock] Persisted chunk '{id}' to MongoDB vector store simulation.")
            except Exception as ex:
                print(f"[VectorDB Mock] Error saving fallback chunk: {ex}")

    async def search(self, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """
        Searches for the nearest neighbors of a query vector in Qdrant or MongoDB simulation.
        """
        if self.qdrant_url:
            headers = {}
            if self.qdrant_api_key:
                headers["api-key"] = self.qdrant_api_key
            try:
                url = self.qdrant_url.rstrip("/")
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.post(
                        f"{url}/collections/{self.collection_name}/points/search",
                        headers=headers,
                        json={
                            "vector": query_vector,
                            "limit": limit,
                            "with_payload": True,
                        },
                    )
                    if resp.status_code == 200:
                        results = resp.json().get("result", [])
                        print(f"[Qdrant] Search found {len(results)} matches.")
                        return [
                            {
                                "id": r.get("id"),
                                "score": r.get("score"),
                                "payload": r.get("payload", {}),
                            }
                            for r in results
                        ]
            except Exception as e:
                print(f"[Qdrant] Search failed on Qdrant: {e}. Using MongoDB fallback.")

        # MongoDB simulation fallback: retrieve all items and calculate cosine similarity
        if self.mongo_collection is not None:
            try:
                cursor = self.mongo_collection.find({})
                results = []
                async for doc in cursor:
                    doc_vec = doc.get("vector", [])
                    if len(doc_vec) == len(query_vector):
                        # Cosine similarity for unit vectors is simply their dot product
                        score = sum(a * b for a, b in zip(query_vector, doc_vec))
                        results.append(
                            {
                                "id": doc.get("_id"),
                                "score": score,
                                "payload": doc.get("payload", {}),
                            }
                        )
                # Sort descending by score
                results.sort(key=lambda x: x["score"], reverse=True)
                print(f"[VectorDB Mock] Simulated vector search matched {len(results)} chunks.")
                return results[:limit]
            except Exception as ex:
                print(f"[VectorDB Mock] Fallback search error: {ex}")

        return []
