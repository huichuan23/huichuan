"""
推荐 API 路由
POST /api/recommend  → DeepSeek 个性化推荐
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import httpx, os, json

from database import get_db, Product

router = APIRouter()

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


class RecommendRequest(BaseModel):
    height:   int
    weight:   int
    skin:     str = "普通肤色"
    face:     str = "普通脸型"
    scene:    str = "日常"
    style:    str = "干净清爽"
    dislike:  Optional[str] = None
    existing: Optional[str] = None
    desc:     Optional[str] = None
    budgets:  dict


def get_body_info(h: int, w: int) -> dict:
    bmi = round(w / (h/100)**2, 1)
    if bmi < 18.5: label = "偏瘦"
    elif bmi < 24: label = "标准"
    elif bmi < 28: label = "略微偏胖"
    else:          label = "偏胖"
    return {"label": label, "bmi": bmi}


def pre_filter(db: Session, category: str, body_label: str, budget: float, limit: int = 15):
    products = db.query(Product)\
        .filter(Product.category == category)\
        .filter(Product.price <= budget)\
        .all()
    result = [p for p in products if body_label not in (p.avoid_body or [])]
    result.sort(key=lambda x: x.price)
    return result[:limit]


@router.post("/recommend")
async def recommend(req: RecommendRequest, db: Session = Depends(get_db)):
    api_key = DEEPSEEK_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")

    body = get_body_info(req.height, req.weight)
    tops    = pre_filter(db, "top",    body["label"], req.budgets.get("top", 100))
    bottoms = pre_filter(db, "bottom", body["label"], req.budgets.get("bottom", 100))
    shoes   = pre_filter(db, "shoes",  body["label"], req.budgets.get("shoes", 150))

    if not tops or not bottoms or not shoes:
        raise HTTPException(status_code=404, detail="预算范围内没有合适商品，请调高预算")

    def fmt(products):
        return "\n".join([
            f"[{p.id}] {p.name} | {p.color} | CA${p.price} | 标签:{','.join(p.tags or [])}"
            for p in products
        ])

    prompt = f"""你是专业男性穿搭顾问，从候选商品中选出3套完整个性化穿搭方案。

【用户信息】
- 身高：{req.height}cm，体重：{req.weight}kg，体型：{body['label']}（BMI {body['bmi']}）
- 肤色：{req.skin}，脸型：{req.face}
- 场景：{req.scene}，风格：{req.style}
- 排斥款式：{req.dislike or '无'}
- 已有单品：{req.existing or '无'}
- 补充描述：{req.desc or '无'}
- 预算：上衣 CA${req.budgets.get('top')}，裤子 CA${req.budgets.get('bottom')}，鞋子 CA${req.budgets.get('shoes')}

【候选上衣】
{fmt(tops)}

【候选裤子】
{fmt(bottoms)}

【候选鞋子】
{fmt(shoes)}

【规则】
1. 只能从候选商品中选，使用商品ID
2. 三套穿搭尽量不重复单品
3. 考虑颜色搭配协调性
4. 考虑肤色和脸型的影响
5. 套装1最安全，套装2有个性，套装3稍冒险

返回严格JSON：
{{"summary":"...","tips":["..."],"outfits":[{{"id":1,"name":"...","safety":"高","reason":"...","top_id":"...","bottom_id":"...","shoes_id":"..."}}]}}"""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "deepseek-chat", "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.7, "max_tokens": 2000, "response_format": {"type": "json_object"}}
        )

    if not resp.is_success:
        raise HTTPException(status_code=502, detail=f"DeepSeek API 错误: {resp.text[:200]}")

    result = json.loads(resp.json()["choices"][0]["message"]["content"])

    def find_product(pid: str):
        p = db.query(Product).filter(Product.id == pid).first()
        if not p: return None
        return {"id": p.id, "name": p.name, "brand": p.brand,
                "price": p.price, "color": p.color, "img": p.img, "buy": p.buy}

    for outfit in result.get("outfits", []):
        outfit["top"]    = find_product(outfit.get("top_id"))
        outfit["bottom"] = find_product(outfit.get("bottom_id"))
        outfit["shoes"]  = find_product(outfit.get("shoes_id"))

    result["body"] = body
    return result
