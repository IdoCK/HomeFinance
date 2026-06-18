from pydantic import BaseModel


class PersonUpdate(BaseModel):
    name: str
