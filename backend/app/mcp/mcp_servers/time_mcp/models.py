from pydantic import BaseModel, Field


class TimeResponse(BaseModel):
    current_time: str = Field(..., description="当前时间，格式为 YYYY-MM-DD HH:MM:SS")
    timezone: str = Field(..., description="时区名称")
    utc_offset: str = Field(..., description="UTC 偏移量，格式为 +HH:MM")
    timestamp: int = Field(..., description="Unix 时间戳")
