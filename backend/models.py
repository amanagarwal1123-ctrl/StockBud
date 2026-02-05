from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone

class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: Optional[str] = None
    date: Optional[str] = None
    type: str
    refno: Optional[str] = None
    party_name: Optional[str] = None
    item_name: str
    stamp: Optional[str] = None
    tag_no: Optional[str] = None
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine: float = 0.0
    labor: float = 0.0
    labor_on: Optional[str] = None
    dia_wt: float = 0.0
    stn_wt: float = 0.0
    tunch: Optional[str] = None
    rate: float = 0.0
    total_pc: int = 0
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    total_amount: float = 0.0
    taxable_value: float = 0.0

class OpeningStock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: Optional[str] = None
    unit: Optional[str] = None
    pc: int = 0
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine: float = 0.0
    labor_wt: float = 0.0
    labor_rs: float = 0.0
    rate: float = 0.0
    total: float = 0.0
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PhysicalStock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: Optional[str] = None
    pc: int = 0
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine: float = 0.0
    verification_date: Optional[str] = None
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MasterItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: str
    gr_wt: float = 0.0
    net_wt: float = 0.0
    is_master: bool = True
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ItemMapping(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_name: str
    master_name: str
    created_by: str = "system"
    created_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PurchaseLedger(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    purchase_tunch: float
    labour_per_kg: float
    total_purchased_kg: float
    total_fine_kg: float
    total_labour: float
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_hash: str
    full_name: str
    role: str
    is_active: bool = True
    created_by: str = "system"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class ActionHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str
    data_snapshot: Dict[str, Any] = {}
    can_undo: bool = True

class ResetRequest(BaseModel):
    password: str
