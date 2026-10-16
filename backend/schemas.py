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
    currency: str = "USD"


class GoalCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    target_amount: float
    saved_amount: float = 0
    target_date: Optional[str] = None
    horizon: str = "short"
    notes: str = ""
    currency: str = "USD"


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
    currency: str = "USD"


class AccountBalanceUpdate(BaseModel):
    balance: float


class AccountSnapshotCreate(BaseModel):
    date: str
    balance: float


class PopulateFromStatements(BaseModel):
    file_hashes: list[str]


class CategoryUpsert(BaseModel):
    person_id: int
    name: str
    keywords: str = ""
    parent: Optional[str] = None


class VendorUpsert(BaseModel):
    person_id: int
    name: str
    keywords: str = ""


class VendorGroup(BaseModel):
    person_id: int
    target: str   # the vendor group to fold into
    keyword: str  # the dragged merchant key to add to that group


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
    currency: str = "USD"
    currency_source: str = "unknown"


class ImportCommit(BaseModel):
    person_id: int
    filename: str
    file_hash: str
    source: str = "auto"
    rows: list[ImportRow]


class FxRateUpsert(BaseModel):
    rate_date: str
    base: str = "USD"
    quote: str = "ILS"
    rate: float


class FxRefresh(BaseModel):
    dates: list[str]
    base: str = "USD"
    quote: str = "ILS"


class FxDisplayRate(BaseModel):
    """Manual set of the single global display rate (no per-date dimension)."""
    base: str = "USD"
    quote: str = "ILS"
    rate: float


class FxDisplayRefresh(BaseModel):
    base: str = "USD"
    quote: str = "ILS"


class EventCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    kind: str = "event"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    rule: Optional[dict] = None


class EventTags(BaseModel):
    transaction_ids: list[int]
