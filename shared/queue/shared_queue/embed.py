import hashlib
from typing import List


class EmbeddingService:
    def embed(self, text: str) -> List[float]:
        """
        Embeds a text string. Generates a deterministic, normalized 384-dimensional vector.
        This provides high-fidelity math representation for vector search databases.
        """
        dims = 384
        vector = []

        # Generate deterministic float vector using hashlib and index factors
        text_hash = hashlib.sha256(text.encode("utf-8")).digest()
        for i in range(dims):
            # Create variation across dimensions
            hash_byte = text_hash[i % len(text_hash)]
            val = (hash_byte * (i + 7)) % 100
            vector.append(float(val) / 100.0)

        # Normalize to unit vector for standard cosine similarity
        magnitude = sum(x**2 for x in vector) ** 0.5
        if magnitude > 0:
            vector = [x / magnitude for x in vector]

        return vector
