from typing import Literal

from pydantic import BaseModel, Field


class Person(BaseModel):
    name: str | None = Field(default="", description="人名称")
    age: Literal[1, 2, 3] = Field(description="年龄")


person = Person.model_validate({"name": None, "age": 4})
print(person)
