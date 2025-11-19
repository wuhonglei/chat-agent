"""
用户认证
"""

from fastapi import APIRouter, HTTPException
from loguru import logger
from sqlmodel import Session
from fastapi import Depends
from app.core.db import get_db
from app.models.response import ApiResponse
from app.models.db import Message

router = APIRouter()
