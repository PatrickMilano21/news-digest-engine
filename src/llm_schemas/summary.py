from __future__ import annotations

from pydantic import BaseModel, Field, model_validator



class Citation(BaseModel):
    """A grounded reference to source material."""
    source_url: str
    evidence_snippet: str

class SummaryResult(BaseModel):
    """
    LLM adapter output contract.
    Either (summary + citations) OR refusal - never both, never neither. 
    """
    summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    #confidence is model-reported self-assess confidence (0.0-1.0), not calibrated.
    #Do not use for decision-making without calibration work. 
    confidence: float | None = None
    refusal: str | None = None

@model_validator(mode='after')
def check_summary_or_refusal(self):
    """Either (summary + citations) OR refusal, never both, never neither."""
    has_summary = self.summary is not None and len(self.summary) > 0
    has_citations = len(self.citations) > 0
    has_refusal = self.refusal is not None and len(self.refusal) > 0

    if has_refusal and has_summary:
        raise ValueError("Cannot have both summary and refusal")
    if not has_refusal and not has_summary:
        raise ValueError("Must have either summary or refusal")
    if has_summary and not has_citations:
        raise ValueError("Summary requires at least one citation")

    return self