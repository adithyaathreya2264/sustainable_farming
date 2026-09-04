"""Import every model so ``Base.metadata`` is fully populated on a single import."""

from backend.models.base import Base, SyncCounter, SyncMixin, TimestampMixin, utcnow
from backend.models.user import User
from backend.models.field import Field
from backend.models.crop import Crop, CropVariety
from backend.models.location import Location
from backend.models.agri_catalog import AgriCatalog, AgriCatalogCategory
from backend.models.crop_growth_stage import CropGrowthStage, DataConfidence
from backend.models.planting import Planting, PlantingStatus
from backend.models.intervention import Intervention, InterventionType
from backend.models.scouting_observation import ScoutingObservation
from backend.models.recommendation import (
    Recommendation,
    RecommendationSeverity,
    RecommendationStatus,
)
from backend.models.agronomic_rule import AgronomicRule
from backend.models.scheme import (
    GovtScheme,
    SchemeMatch,
    SchemeMatchStatus,
    MatchConfidence,
)
from backend.models.otp import OtpRequest

__all__ = [
    "Base",
    "SyncCounter",
    "SyncMixin",
    "TimestampMixin",
    "utcnow",
    "User",
    "Field",
    "Crop",
    "CropVariety",
    "Location",
    "AgriCatalog",
    "AgriCatalogCategory",
    "CropGrowthStage",
    "DataConfidence",
    "Planting",
    "PlantingStatus",
    "Intervention",
    "InterventionType",
    "ScoutingObservation",
    "Recommendation",
    "RecommendationSeverity",
    "RecommendationStatus",
    "AgronomicRule",
    "GovtScheme",
    "SchemeMatch",
    "SchemeMatchStatus",
    "MatchConfidence",
    "OtpRequest",
]
