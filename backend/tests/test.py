from pydantic import BaseModel, Field


class Person(BaseModel):
    name: str | None = Field(default="", description="人名称")


person = Person.model_validate({"name": None})
print(person)
