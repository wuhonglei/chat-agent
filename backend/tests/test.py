from typing import Literal
from pydantic import Field


def test(a: Literal["24h", "72h", "168h"] = Field(default="24h")) -> str:
    return a


print(test('25'))
