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


class AccountCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    kind: str
    is_asset: bool
    balance: float = 0


class AccountBalanceUpdate(BaseModel):
    balance: float
