# schemas.py
from pydantic import BaseModel
from typing import List, Optional

class AssetInfo(BaseModel):
    id: str
    name: str
    type: str
    value: float  # 萬
    rate: float
    monthly_add: float
    add_years: int
    tax_type: str

class TimelineInfo(BaseModel):
    current_age: int
    life_expectancy: int
    retire_age: int

class SimulationRequest(BaseModel):
    timeline: TimelineInfo
    assets: List[AssetInfo]
    insurances: Optional[List[dict]] = []