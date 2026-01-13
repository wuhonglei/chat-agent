from pydantic import BaseModel, ConfigDict


class User(BaseModel):
    name: str
    age: int

    model_config = ConfigDict(extra="allow")


user = User(
    **{
        "name": "John",
        "age": 30,
        "email": {"value": "john@example.com"},
    }
)

print(user.email["value"])

print(hasattr(user, "not_exist"))
