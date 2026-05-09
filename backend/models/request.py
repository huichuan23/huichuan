from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class Scene(str, Enum):
    daily = "日常"
    class_room = "上课"
    date = "约会"
    commute = "通勤"
    sport = "运动"
    formal = "正式场合"


class Style(str, Enum):
    simple = "简单"
    clean = "干净"
    korean = "韩系"
    casual = "休闲"
    minimal = "极简"


class RecommendRequest(BaseModel):
    height: int = Field(..., ge=150, le=220, description="身高（cm）")
    weight: int = Field(..., ge=40, le=150, description="体重（kg）")
    scene: Scene = Field(default=Scene.daily, description="穿搭场景")
    style: Style = Field(default=Style.simple, description="偏好风格")
    budget: Optional[int] = Field(default=None, description="预算上限（元），可选")

    class Config:
        json_schema_extra = {
            "example": {
                "height": 175,
                "weight": 70,
                "scene": "日常",
                "style": "简单",
                "budget": 500
            }
        }


class Product(BaseModel):
    name: str
    category: str  # top / bottom / shoes
    color: str
    price: int
    image_url: str
    buy_url: str
    brand: Optional[str] = None


class Outfit(BaseModel):
    id: int
    name: str
    reason: str          # 推荐理由（核心）
    safety_score: str    # 安全等级：高/中
    top: Product
    bottom: Product
    shoes: Product
    total_price: int


class RecommendResponse(BaseModel):
    user_profile: dict
    body_type: str       # 体型分析结果
    outfits: List[Outfit]
    tips: List[str]      # 额外穿搭小贴士
