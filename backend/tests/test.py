from typing import Optional
from pydantic import BaseModel, Field


class Test(BaseModel):
    name: str = Field(description="name")
    age: Optional[int] = Field(default=None, description="age")


test = Test(name="John")
print(test.model_dump())
