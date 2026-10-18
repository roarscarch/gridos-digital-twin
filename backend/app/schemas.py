"""Pydantic request/response schemas."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class SimulateRequest(BaseModel):
    load_multiplier: float = Field(1.0, ge=0.0, le=5.0)
    solar_multiplier: float = Field(1.0, ge=0.0, le=3.0)
    open_lines: List[str] = Field(default_factory=list, description="Out-of-service line names (N-1 switching)")
    include_alarms: bool = True


class CompareRequest(BaseModel):
    baseline: SimulateRequest = SimulateRequest()
    scenario: SimulateRequest = SimulateRequest(load_multiplier=1.2, solar_multiplier=0.8)


class Violation(BaseModel):
    asset: str
    type: str
    observed: float
    limit: float
    severity: str
    message: str
    priority: Optional[str] = None
    unit: Optional[str] = None


class BusResult(BaseModel):
    name: str
    vn_kv: Optional[float] = None
    voltage_pu: float
    voltage_kv: Optional[float] = None
    angle_deg: Optional[float] = None
    p_mw: Optional[float] = None
    q_mvar: Optional[float] = None


class LineResult(BaseModel):
    name: str
    from_bus: Optional[str] = None
    to_bus: Optional[str] = None
    loading_percent: float
    current_ka: Optional[float] = None
    current_a: Optional[float] = None
    rated_a: Optional[float] = None
    p_from_mw: Optional[float] = None
    p_to_mw: Optional[float] = None
    loss_mw: Optional[float] = None
    q_from_mvar: Optional[float] = None
    in_service: Optional[bool] = True


class TransformerResult(BaseModel):
    name: str = ""
    hv_bus: Optional[str] = None
    lv_bus: Optional[str] = None
    sn_mva: Optional[float] = None
    loading_percent: float = 0.0
    p_hv_mw: Optional[float] = None
    q_hv_mvar: Optional[float] = None
    loss_mw: Optional[float] = None


class SimulateResponse(BaseModel):
    converged: bool
    buses: List[BusResult] = []
    lines: List[LineResult] = []
    transformer: Optional[TransformerResult] = None
    transformer_loading_percent: float = 0.0
    line_losses_mw: float = 0.0
    trafo_losses_mw: float = 0.0
    total_losses_mw: float = 0.0
    total_load_mw: float = 0.0
    total_solar_mw: float = 0.0
    total_q_mvar: float = 0.0
    grid_import_mw: float = 0.0
    grid_import_mvar: float = 0.0
    pf: float = 0.0
    violations: List[Violation] = []
    alarms: List[Violation] = []


class ScenarioCreate(SimulateRequest):
    name: str = "scenario"


class ScenarioRecord(BaseModel):
    id: int
    name: str
    load_multiplier: float
    solar_multiplier: float
    open_lines: List[str] = []
    result: Dict[str, Any]


class EventIn(BaseModel):
    type: str = Field(description="alarm_ack | switching | note | scenario")
    asset: str = ""
    message: str = ""
    actor: str = "operator"


class EventOut(EventIn):
    id: int
    ts: str
