#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据模型定义
"""
from typing import List, Dict, Any
from pydantic import BaseModel, Field

class VideoInfo(BaseModel):
    """视频元数据模型"""
    title: str
    cid: int
    pages: List[Dict[str, Any]] = Field(..., description="分P信息列表") 