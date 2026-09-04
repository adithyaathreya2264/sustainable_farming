"""Growth-stage resolution (Task 4.1).

`typical_days_from_sowing_*` on CropGrowthStage is a heuristic default, not
ground truth — real timing varies with weather. Treat `current_growth_stage`
as an approximation, same caveat as the underlying data.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.base import utcnow
from backend.models.crop_growth_stage import CropGrowthStage
from backend.models.planting import Planting


def current_growth_stage(planting: Planting, db: Session) -> str | None:
    """`None` if before the first seeded stage, after the last, or the crop
    has no seeded stages at all — never raises; an engine calling this treats
    `None` the same as "no stage-gated rule can evaluate right now".
    """
    days_since_sowing = (utcnow().date() - planting.sowing_date).days

    stages = db.scalars(
        select(CropGrowthStage)
        .where(CropGrowthStage.crop_id == planting.crop_id)
        .order_by(CropGrowthStage.stage_order)
    ).all()

    for stage in stages:
        if (
            stage.typical_days_from_sowing_start
            <= days_since_sowing
            < stage.typical_days_from_sowing_end
        ):
            return stage.stage_name

    return None
