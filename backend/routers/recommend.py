"""
推荐 API 路由
POST /api/recommend      → DeepSeek 个性化推荐
POST /api/analyze-body   → DeepSeek Vision 体型分析
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
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
    body_analysis: Optional[str] = None
    measurements:  Optional[dict] = None


class AnalyzeBodyRequest(BaseModel):
    messages: list
    height:   Optional[str] = None
    weight:   Optional[str] = None
    chest:    Optional[str] = None
    waist:    Optional[str] = None
    hip:      Optional[str] = None


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


@router.post("/analyze-body")
async def analyze_body(req: AnalyzeBodyRequest):
    """用 DeepSeek 分析体型照片"""
    api_key = DEEPSEEK_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key 未配置")

    # 构建纯文字 prompt（DeepSeek chat 不支持图片，用文字描述分析）
    measure_text = ""
    if req.chest or req.waist or req.hip:
        measure_text = f"胸围{req.chest or '未知'}cm，腰围{req.waist or '未知'}cm，臀围{req.hip or '未知'}cm"

    prompt = f"""你是专业男性体型分析师和穿搭顾问。请根据用户信息给出专业体型分析和穿搭建议。

用户信息：
- 身高：{req.height or '未知'}cm
- 体重：{req.weight or '未知'}kg
- 三围：{measure_text or '未提供'}

请分析并给出：
1. 体型特征描述（2-3句话，包括体型类型如标准/偏瘦/略胖等）
2. 最适合的版型和款式（具体建议）
3. 应避免的款式（具体说明原因）
4. 颜色搭配建议（适合的颜色系）
5. 3个最重要的穿搭关键词

最后一行格式必须是：标签：XXX|XXX|XXX"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 800
            }
        )

    if not resp.is_success:
        raise HTTPException(status_code=502, detail=f"DeepSeek API 错误: {resp.text[:200]}")

    analysis = resp.json()["choices"][0]["message"]["content"]
    return {"analysis": analysis}


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

    measure_text = ""
    if req.measurements:
        c = req.measurements.get("chest","")
        w = req.measurements.get("waist","")
        h = req.measurements.get("hip","")
        if c or w or h:
            measure_text = f"\n- 三围：胸围{c or '未知'}cm，腰围{w or '未知'}cm，臀围{h or '未知'}cm"

    body_analysis_text = f"\n- AI体型分析：{req.body_analysis}" if req.body_analysis else ""

    prompt = f"""你是专业男性穿搭顾问，从候选商品中选出3套完整个性化穿搭方案。

【用户信息】
- 身高：{req.height}cm，体重：{req.weight}kg，体型：{body['label']}（BMI {body['bmi']}）{measure_text}
- 肤色：{req.skin}，脸型：{req.face}
- 场景：{req.scene}，风格：{req.style}
- 排斥款式：{req.dislike or '无'}
- 已有单品：{req.existing or '无'}
- 补充描述：{req.desc or '无'}{body_analysis_text}

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
4. 重点参考AI体型分析结果（如有）和三围数据来选择合适版型
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
