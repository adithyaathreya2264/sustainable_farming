"""Import every model so ``Base.metadata`` is fully populated on a single import."""

from backend.models.base import Base, SyncCounter, SyncMixin, TimestampMixin, utcnow
from backend.models.user import User
from backend.models.field import Field
from backend.models.planting import Planting, PlantingStatus
from backend.models.intervention import Intervention, InterventionType
from backend.models.recommendation import (
    Recommendation,
    RecommendationSeverity,
    RecommendationStatus,
)
from backend.models.scheme import GovtScheme, SchemeMatch, SchemeMatchStatus
from backend.models.otp import OtpRequest

__all__ = [
    "Base",
    "SyncCounter",
    "SyncMixin",
    "TimestampMixin",
    "utcnow",
    "User",
    "Field",
    "Planting",
    "PlantingStatus",
    "Intervention",
    "InterventionType",
    "Recommendation",
    "RecommendationSeverity",
    "RecommendationStatus",
    "GovtScheme",
    "SchemeMatch",
    "SchemeMatchStatus",
    "OtpRequest",
]
