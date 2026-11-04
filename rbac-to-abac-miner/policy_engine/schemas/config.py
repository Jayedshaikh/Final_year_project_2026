"""Configuration models for policy optimisation.

Owner: Granthali (policy_engine module)
"""
from pydantic import BaseModel, Field


class OptimisationConfig(BaseModel):
    """Configuration for ABAC policy optimisation.
    
    Attributes:
        min_support: Minimum support threshold for rule acceptance [0, 1]
        min_confidence: Minimum confidence threshold for rule acceptance [0, 1]
        confidence_tolerance: Tolerance for confidence drop during generalisation [0, 1]
        wsc_weights: Weights for Weighted Structural Complexity (w_rule, w_cond, w_val)
        random_seed: Random seed for reproducibility
    """
    min_support: float = Field(..., ge=0, le=1)
    min_confidence: float = Field(..., ge=0, le=1)
    confidence_tolerance: float = Field(0.0, ge=0, le=1)
    wsc_weights: dict = Field(
        default={"w_rule": 1.0, "w_cond": 1.0, "w_val": 0.5},
        description="Weights for WSC computation"
    )
    random_seed: int = Field(42)
