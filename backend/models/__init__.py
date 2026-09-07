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

# Dataset-derived reference tables (see datasets/README.md for provenance).
from backend.models.state_baseline import SoilBaseline, StateClimateNormal
from backend.models.yield_benchmark import YieldBenchmark
from backend.models.crop_nutrient_target import CropNutrientTarget
from backend.models.market_price import MarketPrice
from backend.models.crop_disease import CropDisease, CropDiseaseSymptom

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
    "SoilBaseline",
    "StateClimateNormal",
    "YieldBenchmark",
    "CropNutrientTarget",
    "MarketPrice",
    "CropDisease",
    "CropDiseaseSymptom",
]
