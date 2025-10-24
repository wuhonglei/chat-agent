# 方式1：使用验证器
from pydantic import field_validator, validator
from pydantic import BaseModel, Field
from typing import Optional


class YourModel(BaseModel):
    name: str = Field(default="John")
    person: Optional[dict] = Field(default_factory=dict)

    @field_validator('person')
    def validate_person(cls, v):
        if v is None:
            return {}
        return v


model = YourModel(person=None)
print(model)
