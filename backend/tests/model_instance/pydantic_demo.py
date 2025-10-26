# 方式1：使用验证器
from pydantic import field_validator, validator
from pydantic import BaseModel, Field
from typing import Optional


class Person(BaseModel):
    name: str
    age: int
    email: str


class YourModel(BaseModel):
    name: str = Field(default="John")
    person: Optional[Person] = Field(default_factory=dict)

    @field_validator('person')
    def validate_person(cls, v):
        if v is None:
            return {}
        return v


model = YourModel(person=Person(name="John", age=30, email="john@example.com"))
print(model.person.model_dump(exclude_none=True))
