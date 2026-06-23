from pydantic import BaseModel
from typing import Optional


class PersonUpdate(BaseModel):
    name: str


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    included: Optional[bool] = None


class BudgetUpsert(BaseModel):
    person_id: Optional[int] = None
    category: str
    amount: float


class GoalCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    target_amount: float
    saved_amount: float = 0
    target_date: Optional[str] = None
    horizon: str = "short"
    notes: str = ""


class GoalSavedUpdate(BaseModel):
    saved_amount: float


class GoalNotesUpdate(BaseModel):
    notes: str


class AccountCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    kind: str
    is_asset: bool
    balance: float = 0


class AccountBalanceUpdate(BaseModel):
    balance: float


class CategoryUpsert(BaseModel):
    person_id: int
    name: str
    keywords: str = ""
    parent: Optional[str] = None


class VendorUpsert(BaseModel):
    person_id: int
    name: str
    keywords: str = ""


class InsightsRequest(BaseModel):
    person_id: Optional[int] = None


class ImportRow(BaseModel):
    date: str
    description: str
    amount: float
    category: str = "Uncategorized"
    source: str = "auto"
    included: bool = True
    balance: Optional[float] = None


class ImportCommit(BaseModel):
    person_id: int
    filename: str
    file_hash: str
    source: str = "auto"
    rows: list[ImportRow]


class EventCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    kind: str = "event"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rule: Optional[dict] = None


class EventTags(BaseModel):
    transaction_ids: list[int]
