from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    engine_version: str


class SearchCandidate(BaseModel):
    reference_print: str
    score: float


class SearchResponse(BaseModel):
    results: list[SearchCandidate]
    engine_version: str
