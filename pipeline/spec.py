"""
pipeline/spec.py
Pydantic model defining the machine-readable ConstraintSpec.
Source of truth for brief synthesis, grader synthesis, and reward scoring.
"""

from typing import List
from pydantic import BaseModel, Field, field_validator


class PerfConstraint(BaseModel):
    max_draw_calls: int = Field(default=40, ge=1, le=500, description="Maximum permitted WebGL draw calls per frame")
    first_frame_ms: int = Field(default=250, ge=1, le=2000, description="Virtual time deadline for first rendered frame")


class A11yConstraint(BaseModel):
    min_contrast_ratio: float = Field(default=4.5, ge=1.0, le=21.0, description="Minimum WCAG AA text contrast ratio")
    reduced_motion_respected: bool = Field(default=True, description="Whether prefers-reduced-motion must be handled")


class ConstraintSpec(BaseModel):
    task_id: str = Field(description="Kebab-case task identifier derived from seed and index")
    product_category: str = Field(description="Product category, e.g. fintech-app, indie-game, coffee-roaster")
    mood: str = Field(description="Visual mood, e.g. calm, energetic, luxurious, minimal, futuristic, playful")
    palette: List[str] = Field(min_length=3, max_length=5, description="3 to 5 hex color strings, e.g. #0B192C")
    palette_tolerance: float = Field(default=28.0, ge=5.0, le=60.0, description="Maximum allowed CIELAB distance")
    required_copy: List[str] = Field(min_length=1, max_length=10, description="Exact copy strings that must appear in DOM")
    motion_budget_ms: List[int] = Field(min_length=2, max_length=2, description="[min_ms, max_ms] animation duration window")
    allowed_easings: List[str] = Field(min_length=1, description="List of allowed easing identifiers")
    interaction: str = Field(default="none", description="Interaction requirement, e.g. hover-tilt, scroll-parallax, none")
    perf: PerfConstraint = Field(default_factory=PerfConstraint)
    a11y: A11yConstraint = Field(default_factory=A11yConstraint)
    heldout: bool = Field(default=False, description="Whether this task is part of the held-out split")

    @field_validator("palette")
    @classmethod
    def validate_hex_colors(cls, v: List[str]) -> List[str]:
        for col in v:
            if not col.startswith("#") or len(col) not in (4, 7):
                raise ValueError(f"Invalid hex color format: {col}")
        return v

    @field_validator("motion_budget_ms")
    @classmethod
    def validate_budget_order(cls, v: List[int]) -> List[int]:
        if v[0] >= v[1]:
            raise ValueError(f"motion_budget_ms min must be strictly less than max: {v}")
        return v

