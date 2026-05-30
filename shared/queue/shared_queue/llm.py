import os
import httpx
from typing import List, Optional


class LLMService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", None)

    async def generate(self, context_chunks: List[str], query: str) -> str:
        """
        Generates a contextual response using the context chunks and query.
        Falls back to a high-fidelity local keyword and context extraction engine if no API is available.
        """
        context_text = "\n\n".join(context_chunks)
        print(f"[LLM] Generating response for query: '{query}' with {len(context_chunks)} context chunks.")

        if self.api_key:
            # We can invoke a real OpenAI / standard API call if key is present
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": "gpt-4o-mini",
                            "messages": [
                                {
                                    "role": "system",
                                    "content": (
                                        "You are an expert legal AI assistant for KLegally. "
                                        "Answer the query using ONLY the following context. If you cannot find "
                                        "the answer, synthesize the best possible response based on the context."
                                    ),
                                },
                                {
                                    "role": "user",
                                    "content": f"Context:\n{context_text}\n\nQuery: {query}",
                                },
                            ],
                            "temperature": 0.2,
                        },
                    )
                    if resp.status_code == 200:
                        return resp.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                print(f"[LLM] Real API call failed: {e}. Falling back to contextual synthesis engine.")

        # High-fidelity Contextual Synthesis Fallback
        query_words = [w.lower() for w in query.replace("?", "").split() if len(w) > 3]

        # Scan context chunks to find the most relevant sentences
        sentences = []
        for chunk in context_chunks:
            for line in chunk.split("\n"):
                for sentence in line.split(". "):
                    s_clean = sentence.strip()
                    if s_clean:
                        sentences.append(s_clean)

        matched_sentences = []
        for sentence in sentences:
            matches = sum(1 for word in query_words if word in sentence.lower())
            if matches > 0:
                matched_sentences.append((matches, sentence))

        # Sort by match counts descending
        matched_sentences.sort(key=lambda x: x[0], reverse=True)

        if matched_sentences:
            synthesis = " ".join([s[1] for s in matched_sentences[:3]])
            return (
                f"[Simulated AI Response] Based on the document context, {synthesis}."
            )

        # General summary fallback using first available context
        if context_chunks:
            intro = context_chunks[0][:150]
            return (
                f"[Simulated AI Response] The document references the following: '{intro}...'. "
                f"However, specific details matching '{query}' were not explicitly found in the retrieved sections."
            )

        return (
            "[Simulated AI Response] No document context was found to answer this query. "
            "Please upload and ingest a document first."
        )
