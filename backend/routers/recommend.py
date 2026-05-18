"""
推荐 API v3 - 全面体型适配版
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
    height: int
    weight: int
    language: str = "zh"
    skin: str = "普通肤色"
    face: str = "普通脸型"
    scene: str = "日常"
    style: str = "干净清爽"
    dislike: Optional[str] = None
    existing: Optional[str] = None
    desc: Optional[str] = None
    budgets: dict
    body_analysis: Optional[str] = None
    body_issues: Optional[List[str]] = []
    body_issue_rules: Optional[object] = None
    measurements: Optional[dict] = {}

class AnalyzeBodyRequest(BaseModel):
    messages: list
    language: str = "zh"
    height: Optional[str] = None
    weight: Optional[str] = None
    chest: Optional[str] = None
    waist: Optional[str] = None
    hip: Optional[str] = None
    thigh: Optional[str] = None
    calf: Optional[str] = None

ISSUE_PROMPTS = {
    "shoulder_narrow": "用户肩膀较窄，上衣优先选横条纹、oversize、层叠款增加肩宽感，避免无袖和深V",
    "shoulder_wide":   "用户肩膀宽，上衣选深色系和竖条纹收窄，避免横条纹，下装选宽松平衡",
    "belly":           "用户腹部偏圆，上衣必须宽松深色长款遮住腰线，严禁推荐紧身和浅色上衣",
    "arm_thick":       "用户手臂偏粗，避免无袖和紧身袖，选宽松长袖",
    "neck_short":      "用户脖子短，必须避免高领和堆领，选V领或低圆领",
    "thigh_thick":     "用户大腿偏粗，裤子必须直筒或宽松版型，颜色选深色，严禁skinny和浅色裤",
    "calf_thick":      "用户小腿偏粗，选长裤遮盖，避免九分裤和踝靴",
    "leg_short":       "用户腿部偏短，上衣不要过长，裤子选九分或高腰拉长腿部比例",
    "o_leg":           "用户O型腿，必须选宽松直筒深色长裤，严禁紧身裤和短裤",
    "x_leg":           "用户X型腿，选直筒裤，避免过宽松的阔腿裤",
    "hip_big":         "用户臀部丰满，上衣选长款遮臀，裤子深色宽松，避免浅色紧身裤",
    "back_wide":       "用户背部宽，上衣选深色系收窄，避免横条纹",
    "leg_long":        "用户腿长是优势，可大胆选九分裤和阔腿裤展示腿型",
    "waist_thin":      "用户腰细是优势，可以tucked in展示腰线，配高腰裤更好看",
    "shoulder_good":   "用户肩型好是优势，选修身款展现肩线",
    "body_fit":        "用户身材匀称，重点按风格偏好推荐",
    "tall":            "用户身高优势，长款和阔腿裤都能驾驭",
}

STYLE_RULES_2025 = {
    "韩系": {"colors":"黑白灰+莫兰迪色系","tops":"oversize卫衣、简约polo、针织衫","bottoms":"直筒牛仔、宽松休闲裤","shoes":"白色运动鞋、乐福鞋","formula":"oversize上衣+直筒裤+白鞋","forbidden":"荧光色、大logo"},
    "干净清爽": {"colors":"白色、浅灰、米色为主不超过3色","tops":"白色T恤、简约衬衫","bottoms":"直筒裤、卡其裤","shoes":"白色运动鞋","formula":"白T+深色直筒裤+白鞋","forbidden":"大logo、荧光色"},
    "Quiet Luxury": {"colors":"驼色、米白、深灰、藏蓝","tops":"羊绒毛衣、针织衫、polo","bottoms":"修身西裤、质感休闲裤","shoes":"皮鞋、乐福鞋","formula":"羊绒针织+修身西裤+皮鞋","forbidden":"大logo、亮色、工装"},
    "简单百搭": {"colors":"黑白灰+海军蓝","tops":"基础T恤、卫衣、衬衫","bottoms":"深色牛仔、黑色休闲裤","shoes":"经典运动鞋","formula":"基础T+深色牛仔+运动鞋","forbidden":"过于另类设计"},
    "街头": {"colors":"黑色为主可加撞色","tops":"oversized卫衣、宽大T恤","bottoms":"宽松工装裤、baggy牛仔","shoes":"厚底运动鞋、高帮板鞋","formula":"oversize卫衣+宽松工装裤+厚底鞋","forbidden":"正装西裤、皮鞋"},
    "美式休闲": {"colors":"牛仔蓝、白色、卡其、墨绿","tops":"格纹衬衫、印花T恤","bottoms":"宽松牛仔、工装裤","shoes":"靴子、运动鞋","formula":"法兰绒衬衫+宽松牛仔+靴子","forbidden":"修身正装"},
    "极简": {"colors":"黑白灰，最多双色","tops":"纯色T恤、极简针织衫","bottoms":"黑色或灰色直筒裤","shoes":"全白或全黑简洁运动鞋","formula":"单色上下+同色系鞋","forbidden":"任何logo、印花"},
    "日系": {"colors":"大地色系、米色、深蓝、橄榄绿","tops":"工装衬衫、宽松圆领T","bottoms":"宽松锥形裤、工装裤","shoes":"低帮帆布鞋、皮质运动鞋","formula":"工装衬衫+锥形裤+帆布鞋","forbidden":"荧光色、大logo"},
}

def get_body_info(h, w):
    bmi = round(w/(h/100)**2, 1)
    if bmi < 18.5: label = "偏瘦"
    elif bmi < 24: label = "标准"
    elif bmi < 28: label = "略微偏胖"
    else:          label = "偏胖"
    return {"label": label, "bmi": bmi}

def get_measurement_rules(m):
    parts = []
    thigh = float(m.get("thigh") or 0)
    waist = float(m.get("waist") or 0)
    hip   = float(m.get("hip") or 0)
    calf  = float(m.get("calf") or 0)
    if thigh > 62: parts.append("大腿围超过62cm，裤子必须选直筒或宽松，严禁skinny")
    if waist > 90: parts.append("腰围超过90cm，上衣必须宽松遮腰，裤子不能过紧")
    if hip > 105:  parts.append("臀围超过105cm，裤子选深色宽松，上衣长款遮臀")
    if calf > 40:  parts.append("小腿围超过40cm，选长裤遮盖，避免九分裤")
    return parts

def smart_filter(db, category, body_label, budget, body_issues, measurements, limit=18):
    categories = category if isinstance(category, (list, tuple, set)) else [category]
    products = db.query(Product).filter(Product.category.in_(categories)).filter(Product.price<=budget).all()
    result = [p for p in products if body_label not in (p.avoid_body or [])]

    thigh = float(measurements.get("thigh") or 0)
    waist = float(measurements.get("waist") or 0)

    primary_category = categories[0] if categories else category

    if primary_category == "bottom":
        if thigh > 62 or "thigh_thick" in body_issues or "o_leg" in body_issues:
            result = [p for p in result if not any(t in (p.tags or []) for t in ["skinny","slim"])]
    if primary_category == "top":
        if "belly" in body_issues or waist > 90:
            result = [p for p in result if "fitted" not in (p.tags or [])]
    if primary_category == "top":
        if "neck_short" in body_issues:
            result = [p for p in result if "turtleneck" not in p.name.lower()]

    def score(p):
        s = 0
        tags = p.tags or []
        if "thigh_thick" in body_issues and primary_category=="bottom":
            if any(t in tags for t in ["straight","relaxed","wide"]): s += 3
            if p.color_tone == "dark": s += 2
        if "belly" in body_issues and primary_category=="top":
            if p.color_tone == "dark": s += 2
        if "o_leg" in body_issues and primary_category=="bottom":
            if p.color_tone == "dark": s += 2
        return s

    result.sort(key=score, reverse=True)
    return result[:limit]

def build_body_prompt(body_issues, measurements, body_analysis, skin, face):
    parts = []
    m = measurements or {}

    vals = []
    for k,v in [("胸围","chest"),("腰围","waist"),("臀围","hip"),("大腿围","thigh"),("小腿围","calf")]:
        if m.get(v): vals.append(f"{k}{m[v]}cm")
    if vals: parts.append(f"三围数据：{'、'.join(vals)}")

    measure_rules = get_measurement_rules(m)
    parts.extend(measure_rules)

    if body_issues:
        labels = {
            "shoulder_narrow":"肩膀窄","shoulder_wide":"肩膀宽","belly":"小肚腩",
            "arm_thick":"手臂粗","neck_short":"脖子短","thigh_thick":"大腿粗",
            "calf_thick":"小腿粗","leg_short":"腿短","o_leg":"O型腿","x_leg":"X型腿",
            "hip_big":"臀部丰满","hip_flat":"臀部扁平","back_wide":"背部宽厚",
            "chest_flat":"胸肌不明显","leg_long":"腿长(优势)","waist_thin":"腰细(优势)",
            "shoulder_good":"肩型好(优势)","body_fit":"身材匀称","tall":"身高优势",
        }
        parts.append(f"用户身体特征：{','.join(labels.get(i,i) for i in body_issues)}")
        for i in body_issues:
            if i in ISSUE_PROMPTS: parts.append(ISSUE_PROMPTS[i])

    if body_analysis: parts.append(f"AI体型分析：{body_analysis[:200]}")

    face_rules = {"圆脸":"圆脸选V领或开领拉长脸部","长脸":"长脸可选高领或圆领","方脸":"方脸选圆领柔化轮廓"}
    skin_rules = {"偏白肤色":"肤色偏白，彩色深色都适合","偏黄肤色":"肤色偏黄，选米白驼色深蓝，避免黄橙","偏深肤色":"肤色偏深，白色亮色深色都好"}
    if face in face_rules: parts.append(face_rules[face])
    if skin in skin_rules: parts.append(skin_rules[skin])

    return "\n".join(f"- {p}" for p in parts) if parts else "- 无特殊体型限制"

def build_style_prompt(style, scene):
    rule = STYLE_RULES_2025.get(style, {})
    if not rule: return f"风格：{style}，场景：{scene}"
    return f"""风格：{style}（场景：{scene}）
- 颜色：{rule.get('colors','')}
- 上衣：{rule.get('tops','')}
- 裤子：{rule.get('bottoms','')}
- 鞋子：{rule.get('shoes','')}
- 公式：{rule.get('formula','')}
- 禁忌：{rule.get('forbidden','')}"""

@router.post("/analyze-body")
async def analyze_body(req: AnalyzeBodyRequest):
    api_key = DEEPSEEK_API_KEY
    if not api_key: raise HTTPException(400, "DeepSeek API Key 未配置")
    vals = []
    for k,v in [("胸围",req.chest),("腰围",req.waist),("臀围",req.hip),("大腿围",req.thigh),("小腿围",req.calf)]:
        if v: vals.append(f"{k}{v}cm")
    measure_text = "、".join(vals) if vals else "未提供"
    language_rule = (
        "Write the whole answer in natural English. End with: Tags: tag1|tag2|tag3"
        if req.language == "en"
        else "请使用简体中文。最后一行：标签：XXX|XXX|XXX"
    )
    prompt = f"""你是专业男性体型分析师。根据用户信息给出体型分析。
用户：身高{req.height or '未知'}cm，体重{req.weight or '未知'}kg，数据：{measure_text}
请简洁分析：1.体型特征 2.适合版型 3.避免款式 4.颜色建议 5.三个标签
{language_rule}"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.deepseek.com/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],"temperature":0.7,"max_tokens":600})
    if not resp.is_success: raise HTTPException(502, f"DeepSeek错误: {resp.text[:200]}")
    return {"analysis": resp.json()["choices"][0]["message"]["content"]}

@router.post("/recommend")
async def recommend(req: RecommendRequest, db: Session = Depends(get_db)):
    api_key = DEEPSEEK_API_KEY
    if not api_key: raise HTTPException(400, "DeepSeek API Key 未配置")

    body = get_body_info(req.height, req.weight)
    body_issues = req.body_issues or []
    measurements = req.measurements or {}

    tops    = smart_filter(db,"top",    body["label"],req.budgets.get("top",100),   body_issues,measurements)
    bottoms = smart_filter(db,"bottom", body["label"],req.budgets.get("bottom",100),body_issues,measurements)
    shoes   = smart_filter(db,"shoes",  body["label"],req.budgets.get("shoes",150), body_issues,measurements)
    outerwear = smart_filter(db, ["outerwear", "outer", "jacket", "coat"], body["label"], req.budgets.get("outerwear", 0) or 0, body_issues, measurements, limit=8) if req.budgets.get("outerwear", 0) else []
    hats = smart_filter(db, ["hat", "hats"], body["label"], req.budgets.get("hat", 0) or 0, body_issues, measurements, limit=8) if req.budgets.get("hat", 0) else []
    accessories = smart_filter(db, ["accessory", "accessories"], body["label"], req.budgets.get("accessory", 0) or 0, body_issues, measurements, limit=8) if req.budgets.get("accessory", 0) else []

    if not tops or not bottoms or not shoes:
        raise HTTPException(404, "预算范围内没有合适商品，请调高预算")

    def fmt(products, n=15):
        return "\n".join([f"[{p.id}] {p.name} | 颜色:{p.color} | CA${p.price} | 版型:{p.fit or 'regular'} | 标签:{','.join(p.tags or [])}" for p in products[:n]])

    def optional_section(title, products):
        return f"\n【{title}】\n{fmt(products, 8)}" if products else ""

    optional_budget_text = []
    if req.budgets.get("outerwear"): optional_budget_text.append(f"外套CA${req.budgets.get('outerwear')}")
    if req.budgets.get("hat"): optional_budget_text.append(f"帽子CA${req.budgets.get('hat')}")
    if req.budgets.get("accessory"): optional_budget_text.append(f"配饰CA${req.budgets.get('accessory')}")
    optional_budget_text = "，" + "，".join(optional_budget_text) if optional_budget_text else ""

    body_prompt  = build_body_prompt(body_issues,measurements,req.body_analysis or "",req.skin,req.face)
    style_prompt = build_style_prompt(req.style, req.scene)

    output_language = "English" if req.language == "en" else "Chinese"
    language_rule = (
        "Return every user-facing JSON value in natural English. "
        "Use safety values High, Medium, or Low. Do not use Chinese in summary, tips, outfit names, safety, or reason."
        if req.language == "en"
        else "所有面向用户的 JSON 文案都使用简体中文。safety 使用 高、中、低。"
    )

    prompt = f"""你是专业男性穿搭顾问，必须严格遵守体型规则，从候选商品中选出3套穿搭。
输出语言：{output_language}
语言规则：{language_rule}

【用户信息】
- 身高{req.height}cm，体重{req.weight}kg，体型{body['label']}（BMI {body['bmi']}）
- 场景：{req.scene}，排斥：{req.dislike or '无'}，已有：{req.existing or '无'}
- 补充：{req.desc or '无'}
- 预算：上衣CA${req.budgets.get('top')}，裤子CA${req.budgets.get('bottom')}，鞋子CA${req.budgets.get('shoes')}{optional_budget_text}

【⚠️ 体型约束（最高优先级）】
{body_prompt}

【风格规则】
{style_prompt}

【候选上衣】
{fmt(tops)}

【候选裤子】
{fmt(bottoms)}

【候选鞋子】
{fmt(shoes)}
{optional_section("候选外套（可选）", outerwear)}
{optional_section("候选帽子（可选）", hats)}
{optional_section("候选配饰（可选）", accessories)}

规则：1.只能选候选商品 2.体型约束高于一切 3.三套不重复 4.颜色协调 5.reason说明为何适合此体型 6.严格遵守输出语言 7.上衣、裤子、鞋子必选；外套、帽子、配饰有合适候选时可选，没有合适候选可返回 null

返回JSON：{{"summary":"体型风格总结","tips":["体型贴士1","贴士2","贴士3"],"outfits":[{{"id":1,"name":"...","safety":"高","reason":"具体说明适合体型原因","top_id":"...","bottom_id":"...","shoes_id":"...","outerwear_id":null,"hat_id":null,"accessory_id":null}}]}}"""

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post("https://api.deepseek.com/chat/completions",
            headers={"Authorization":f"Bearer {api_key}","Content-Type":"application/json"},
            json={"model":"deepseek-chat","messages":[{"role":"user","content":prompt}],
                  "temperature":0.6,"max_tokens":2000,"response_format":{"type":"json_object"}})

    if not resp.is_success: raise HTTPException(502, f"DeepSeek错误: {resp.text[:200]}")

    result = json.loads(resp.json()["choices"][0]["message"]["content"])

    def find_product(pid):
        p = db.query(Product).filter(Product.id==pid).first()
        if not p: return None
        return {"id":p.id,"name":p.name,"brand":p.brand,"price":p.price,"color":p.color,"img":p.img,"buy":p.buy}

    for outfit in result.get("outfits",[]):
        outfit["top"]    = find_product(outfit.get("top_id"))
        outfit["bottom"] = find_product(outfit.get("bottom_id"))
        outfit["shoes"]  = find_product(outfit.get("shoes_id"))
        outfit["outerwear"] = find_product(outfit.get("outerwear_id"))
        outfit["hat"] = find_product(outfit.get("hat_id"))
        outfit["accessory"] = find_product(outfit.get("accessory_id"))

    if req.language == "en":
        body_labels_en = {
            "偏瘦": "Slim",
            "标准": "Standard",
            "略微偏胖": "Slightly Stocky",
            "偏胖": "Stocky",
        }
        result["body"] = {**body, "label": body_labels_en.get(body["label"], body["label"])}
    else:
        result["body"] = body
    return result
