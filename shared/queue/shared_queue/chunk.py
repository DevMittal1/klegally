from typing import List, Dict, Any


class Chunk:
    def __init__(self, text: str, metadata: Dict[str, Any]):
        self.text = text
        self.metadata = metadata


class ChunkService:
    def create_chunks(self, pages: List[Dict[str, Any]]) -> List[Chunk]:
        """
        Takes a list of page dicts (containing page_number, content) and chunks the text.
        """
        chunks = []
        for page in pages:
            page_number = page.get("page_number", 0)
            content = page.get("content", {})
            text = content.get("text", "")

            # Split paragraphs
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p_idx, p in enumerate(paragraphs):
                # Also split long paragraphs into ~500 char sub-chunks if needed
                if len(p) > 800:
                    words = p.split()
                    sub_chunk = []
                    sub_len = 0
                    for w in words:
                        sub_chunk.append(w)
                        sub_len += len(w) + 1
                        if sub_len > 500:
                            chunks.append(
                                Chunk(
                                    text=" ".join(sub_chunk),
                                    metadata={
                                        "page_number": page_number,
                                        "paragraph_index": p_idx,
                                        **content.get("metadata", {}),
                                    },
                                )
                            )
                            sub_chunk = []
                            sub_len = 0
                    if sub_chunk:
                        chunks.append(
                            Chunk(
                                text=" ".join(sub_chunk),
                                metadata={
                                    "page_number": page_number,
                                    "paragraph_index": p_idx,
                                    **content.get("metadata", {}),
                                },
                            )
                        )
                else:
                    chunks.append(
                        Chunk(
                            text=p,
                            metadata={
                                "page_number": page_number,
                                "paragraph_index": p_idx,
                                **content.get("metadata", {}),
                            },
                        )
                    )

        # Fallback if no chunks
        if not chunks:
            chunks.append(
                Chunk(
                    text="Document has no readable text.",
                    metadata={"page_number": 1, "empty": True},
                )
            )

        return chunks
