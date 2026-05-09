# 会穿 · AI 男性穿搭助手

> 帮不会穿搭的男生，快速获得 3 套不踩雷的搭配 + 可直接购买的商品链接

---

## 快速启动

### 后端 (FastAPI)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

API 文档：http://localhost:8000/docs

### 前端

直接用浏览器打开 `frontend/index.html` 即可（纯静态页面）

---

## 核心 API

### POST /api/recommend

**请求体：**
```json
{
  "height": 175,
  "weight": 70,
  "scene": "约会",
  "style": "韩系",
  "budget": 800
}
```

**响应：**
```json
{
  "body_type": "标准（BMI 22.9）",
  "user_profile": {...},
  "outfits": [
    {
      "id": 1,
      "name": "核心基础款",
      "reason": "约会场景首选，韩系风格，标准体型不踩雷",
      "safety_score": "高",
      "top":    {"name":"...", "price": 199, "buy_url": "..."},
      "bottom": {"name":"...", "price": 249, "buy_url": "..."},
      "shoes":  {"name":"...", "price": 459, "buy_url": "..."},
      "total_price": 907
    }
  ],
  "tips": ["✅ 你的体型适合：任何版型均适合"]
}
```

---

## 项目架构

```
huichuan/
├── backend/
│   ├── main.py               # FastAPI 入口
│   ├── routers/recommend.py  # POST /recommend 路由
│   ├── core/recommender.py   # 推荐引擎（Rule-based）
│   ├── models/request.py     # Pydantic 请求/响应模型
│   ├── data/products.json    # 商品数据库
│   └── requirements.txt
├── frontend/index.html       # 单页前端（无框架）
└── README.md
```

---

## 推荐逻辑（Rule-based）

```
用户输入 (身高, 体重, 场景, 风格)
    ↓
体型分析 → BMI → 体型标签 + 穿搭禁忌
    ↓
场景/风格 → tags 集合
    ↓
商品打分 = 场景匹配 × 2 + 风格匹配 × 1.5 + 安全色加分 - 禁忌扣分
    ↓
每个类目（上衣/裤子/鞋）取最高分商品
    ↓
组合 → 3 套（不重复选品）
```

---

## Step 5：扩展路线图

### 阶段 1（当前 MVP）
- [x] Rule-based 推荐引擎
- [x] 体型 / 场景 / 风格分析
- [x] 静态商品数据库
- [x] 前端展示 + 购买链接跳转

### 阶段 2：风格理解（LLM）
接入 Claude API，让用户可以用自然语言描述：
```python
# style_parser.py
async def parse_style_input(text: str) -> dict:
    # 调用 Claude，解析 "我想穿简单但有点帅的"
    # 返回 {"tags": ["clean", "smart_casual"], "avoid": ["花里胡哨"]}
```

### 阶段 3：真实商品数据库
- 接入淘宝 / 京东 / POIZON 联盟 API
- 定时爬取价格、库存、图片
- SQLite → PostgreSQL

### 阶段 4：AI 试穿（Try-on）
```python
# tryon.py - 接入 IDM-VTON 或 CatVTON
async def virtual_tryon(user_photo: bytes, garment_image: bytes) -> bytes:
    # 调用开源试穿模型或 API
    # 返回合成后的效果图
```
推荐模型：
- IDM-VTON (HuggingFace)
- CatVTON (开源，效果好)
- Fashn.ai API（付费，简单接入）

### 阶段 5：商业化
- Affiliate 分佣链接（淘宝联盟/京东联盟）
- 用户历史记录（记住偏好）
- 穿搭分享功能

---

## 设计原则

1. **最多 3 套** — 减少选择焦虑
2. **推荐必须安全** — 优先百搭色系
3. **规则优先于 AI** — 逻辑清晰，可调试
4. **可直接购买** — 每件单品都有链接
