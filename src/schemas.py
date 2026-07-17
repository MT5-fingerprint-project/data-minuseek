from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class SearchCandidate(BaseModel):
    reference_print: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchCandidate]
