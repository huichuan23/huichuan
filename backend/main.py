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
    allow_origins=[origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "*").split(",") if origin.strip()],
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
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(400, "只支持 JPG / PNG / WebP 格式")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "图片不能超过 10MB")
    b64 = base64.b64encode(content).decode("utf-8")
    return {"url": f"data:{file.content_type};base64,{b64}"}
