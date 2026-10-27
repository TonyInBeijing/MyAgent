"""Example HTTP routes."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["example"])


class HelloResponse(BaseModel):
    message: str = Field(examples=["Hello from MyAgent"])


@router.get("/hello", response_model=HelloResponse, summary="示例接口")
async def hello() -> HelloResponse:
    """返回一条固定问候，用来确认服务已启动。"""
    return HelloResponse(message="Hello from MyAgent")
