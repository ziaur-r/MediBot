from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    source_document: str
    collection: str
    access_roles: list[str]
    section_title: str
    chunk_type: str = Field(pattern="^(text|table|heading|code)$")


class Chunk(BaseModel):
    id: str
    content: str
    metadata: ChunkMetadata
