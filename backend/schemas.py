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
