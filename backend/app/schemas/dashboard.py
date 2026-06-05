from app.schemas.common import ORMBase


class DashboardStat(ORMBase):
    label: str
    value: str
    note: str | None = None


class MaterializationItem(ORMBase):
    name: str
    status: str
    time: str


class PromotionItem(ORMBase):
    model: str
    stage: str
    time: str


class DashboardSummary(ORMBase):
    stats: list[DashboardStat]
    recent_materializations: list[MaterializationItem]
    recent_promotions: list[PromotionItem]
