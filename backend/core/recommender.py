"""
推荐引擎 - Rule-based 规则系统
优先级：规则 > AI，逻辑清晰可扩展
"""
import json
import os
from typing import List, Dict, Any


DATA_PATH = os.path.join(os.path.dirname(__file__), "../data/products.json")


# ─── 体型分析 ──────────────────────────────────────────────
def analyze_body_type(height: int, weight: int) -> dict:
    """
    计算 BMI，返回体型标签和穿搭禁忌
    """
    bmi = weight / ((height / 100) ** 2)

    if bmi < 18.5:
        return {
            "label": "偏瘦",
            "bmi": round(bmi, 1),
            "avoid": ["宽松大廓形外套", "垂感过强的裤子"],
            "prefer": ["层叠穿搭", "有结构感的单品", "浅色系"],
            "fit_rule": "slim_fit"
        }
    elif bmi < 24:
        return {
            "label": "标准",
            "bmi": round(bmi, 1),
            "avoid": [],
            "prefer": ["任何版型均适合"],
            "fit_rule": "any"
        }
    elif bmi < 28:
        return {
            "label": "略微偏胖",
            "bmi": round(bmi, 1),
            "avoid": ["紧身 T 恤", "浅色横条纹", "高腰短上衣"],
            "prefer": ["深色系", "直筒版型", "竖条纹"],
            "fit_rule": "relaxed_fit"
        }
    else:
        return {
            "label": "偏胖",
            "bmi": round(bmi, 1),
            "avoid": ["紧身款", "浅色系上衣", "短款外套"],
            "prefer": ["深色系", "宽松直筒", "V 领"],
            "fit_rule": "loose_fit"
        }


def analyze_height_rule(height: int) -> dict:
    """
    身高规则：影响裤长和外套选择
    """
    if height < 168:
        return {
            "avoid": ["长款大衣（过膝）", "超长卫衣"],
            "prefer": ["九分裤（视觉拉腿）", "高腰款"],
            "note": "矮个子"
        }
    elif height < 180:
        return {"avoid": [], "prefer": [], "note": "标准身高"}
    else:
        return {
            "avoid": [],
            "prefer": ["长款外套可驾驭", "阔腿裤"],
            "note": "高个子"
        }


# ─── 场景 × 风格映射 ──────────────────────────────────────
SCENE_RULES = {
    "日常":   {"formality": 1, "tags": ["casual", "basic"]},
    "上课":   {"formality": 1, "tags": ["casual", "basic", "clean"]},
    "约会":   {"formality": 2, "tags": ["clean", "smart_casual", "korean"]},
    "通勤":   {"formality": 2, "tags": ["smart_casual", "clean", "basic"]},
    "运动":   {"formality": 1, "tags": ["sport", "casual"]},
    "正式场合": {"formality": 3, "tags": ["formal", "smart_casual"]},
}

STYLE_TAGS = {
    "简单":  ["basic", "casual"],
    "干净":  ["clean", "basic", "smart_casual"],
    "韩系":  ["korean", "clean", "smart_casual"],
    "休闲":  ["casual", "basic"],
    "极简":  ["minimal", "clean", "basic"],
}


# ─── 商品匹配 ─────────────────────────────────────────────
def load_products() -> Dict[str, List[dict]]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # 按 category 分组
    grouped = {"top": [], "bottom": [], "shoes": []}
    for p in data["products"]:
        cat = p.get("category")
        if cat in grouped:
            grouped[cat].append(p)
    return grouped


def score_product(product: dict, body_info: dict, height_info: dict,
                  scene_tags: list, style_tags: list, budget: int = None) -> float:
    """
    给每件商品打分，分数越高越推荐
    """
    score = 0.0

    # 场景标签匹配
    p_tags = product.get("tags", [])
    scene_match = len(set(p_tags) & set(scene_tags))
    style_match = len(set(p_tags) & set(style_tags))
    score += scene_match * 2.0
    score += style_match * 1.5

    # 安全色加分
    if product.get("color_safe"):
        score += 1.5

    # 体型规则
    avoid_keywords = body_info.get("avoid", []) + height_info.get("avoid", [])
    for kw in avoid_keywords:
        if kw in product.get("name", "") or kw in product.get("description", ""):
            score -= 3.0

    # 预算过滤
    if budget and product.get("price", 9999) > budget * 0.5:
        score -= 1.0

    return score


def pick_best_product(products: list, body_info: dict, height_info: dict,
                       scene_tags: list, style_tags: list,
                       budget: int = None, exclude_ids: list = None) -> dict:
    """
    从候选商品中选出得分最高的一件
    """
    exclude_ids = exclude_ids or []
    candidates = [p for p in products if p["id"] not in exclude_ids]
    if not candidates:
        return products[0]  # fallback

    scored = [
        (p, score_product(p, body_info, height_info, scene_tags, style_tags, budget))
        for p in candidates
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


# ─── 生成推荐套装 ──────────────────────────────────────────
def generate_outfits(height: int, weight: int, scene: str,
                     style: str, budget: int = None) -> dict:
    """
    核心推荐函数，返回 1-3 套穿搭
    """
    body_info = analyze_body_type(height, weight)
    height_info = analyze_height_rule(height)
    products = load_products()

    scene_tags = SCENE_RULES.get(scene, SCENE_RULES["日常"])["tags"]
    style_tags = STYLE_TAGS.get(style, STYLE_TAGS["简单"])

    # 生成 3 套，每套选最优不重复组合
    outfits = []
    used_tops = []
    used_bottoms = []
    used_shoes = []

    outfit_configs = [
        {
            "id": 1,
            "theme": "核心基础款",
            "reason_template": "百搭安全，{scene}场景首选，{body_note}不出错"
        },
        {
            "id": 2,
            "theme": "进阶搭配",
            "reason_template": "在基础款上增加细节，{style}风格更明显，适合想稍微变帅的场景"
        },
        {
            "id": 3,
            "theme": "备选方案",
            "reason_template": "同样安全，换个配色，适合{scene}时想有点不同的心情"
        },
    ]

    for cfg in outfit_configs:
        top = pick_best_product(
            products["top"], body_info, height_info,
            scene_tags, style_tags, budget, exclude_ids=used_tops
        )
        bottom = pick_best_product(
            products["bottom"], body_info, height_info,
            scene_tags, style_tags, budget, exclude_ids=used_bottoms
        )
        shoes = pick_best_product(
            products["shoes"], body_info, height_info,
            scene_tags, style_tags, budget, exclude_ids=used_shoes
        )

        used_tops.append(top["id"])
        used_bottoms.append(bottom["id"])
        used_shoes.append(shoes["id"])

        total = top["price"] + bottom["price"] + shoes["price"]
        body_note = body_info["label"] + "体型" if body_info["label"] != "标准" else "标准体型"

        reason = cfg["reason_template"].format(
            scene=scene,
            style=style,
            body_note=body_note
        )

        outfits.append({
            "id": cfg["id"],
            "name": cfg["theme"],
            "reason": reason,
            "safety_score": "高" if cfg["id"] == 1 else "中",
            "top": top,
            "bottom": bottom,
            "shoes": shoes,
            "total_price": total
        })

    # 穿搭贴士
    tips = []
    for avoid in body_info["avoid"][:2]:
        tips.append(f"⚠️ 你的体型建议避免：{avoid}")
    for prefer in body_info["prefer"][:2]:
        tips.append(f"✅ 你的体型适合：{prefer}")
    if height_info["note"] == "矮个子":
        tips.append("📏 身高建议：选九分裤或浅色下装，视觉拉长身材")

    return {
        "user_profile": {
            "height": height,
            "weight": weight,
            "scene": scene,
            "style": style,
        },
        "body_type": f"{body_info['label']}（BMI {body_info['bmi']}）",
        "outfits": outfits,
        "tips": tips
    }
