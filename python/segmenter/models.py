"""Data models for the segmentation engine.

Deliberately plain (stdlib dataclasses only) so the structures port 1:1 to C#
classes when we do the final port. No external dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PageDecision:
    """The engine's per-page verdict. Mirrors the C# PageDecision class."""
    page_index: int                      # 0-based position in the batch
    best_doc_type: str                   # best matching known type (raw name)
    doc_type_confidence: float           # 0..1
    effective_type: str                  # best_doc_type, or "Unknown" if below threshold
    is_start_page: bool
    start_score: float                   # raw additive start score (pre-threshold)
    is_unknown: bool
    needs_review: bool
    extracted_ids: List[str] = field(default_factory=list)
    page_number: Optional[int] = None    # parsed "current" page number, if any
    total_pages: Optional[int] = None    # parsed "of N", if any
    signals: List[str] = field(default_factory=list)  # human-readable reasons
    type_scores: Dict[str, float] = field(default_factory=dict)


@dataclass
class DocumentSegment:
    """A contiguous run of pages forming one logical document.

    start_page/end_page are inclusive, 0-based. Mirrors the C# DocumentSegment
    and maps directly onto a TTA SplitDocumentInfo (SplitIndex = start_page).
    """
    start_page: int
    end_page: int
    doc_type: str
    confidence: float
    needs_review: bool
    reason: str = ""
    ids: List[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page + 1
