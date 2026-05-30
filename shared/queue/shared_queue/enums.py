from enum import Enum


class DocumentStatus(str, Enum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    PARSED = "PARSED"
    CHUNKING = "CHUNKING"
    CHUNKED = "CHUNKED"
    EMBEDDING = "EMBEDDING"
    EMBEDDED = "EMBEDDED"
    FAILED = "FAILED"


class EmbeddingStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
