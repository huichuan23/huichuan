import os
import base64

import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from routers.recommend import router as recommend_router
from routers.products import router as products_router
from database import init_db

app = FastAPI(title="会穿 · AI 男性穿搭助手 API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(recommend_router, prefix="/api")
app.include_router(products_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "ok", "message": "会穿 API v2.1"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    接收图片，返回 base64 data URL。
    Fashn.ai v1.6 支持 base64，无需公开 URL，
    避免 Railway 文件系统临时性导致的图片丢失问题。
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "只支持 JPG / PNG / WebP 格式")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 10MB")
    b64 = base64.b64encode(content).decode("utf-8")
    data_url = f"data:{file.content_type};base64,{b64}"
    return {"url": data_url}


@app.get("/api/fetch-image")
async def fetch_image(url: str = Query(...)):
    """
    后端中转：获取外部图片 URL 并返回 base64。
    用于前端无法直接 fetch 跨域图片（如 Amazon CDN）的情况。
    """
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "无效的图片 URL")
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; HuiChuan/1.0)"
            })
        if resp.status_code != 200:
            raise HTTPException(502, f"图片获取失败: HTTP {resp.status_code}")
        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        b64 = base64.b64encode(resp.content).decode("utf-8")
        return {"base64": b64, "content_type": content_type}
    except httpx.TimeoutException:
        raise HTTPException(504, "图片获取超时")
    except Exception as e:
        raise HTTPException(502, f"图片获取失败: {str(e)}")
