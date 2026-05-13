import os
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routers.recommend import router as recommend_router
from routers.products import router as products_router
from database import init_db

app = FastAPI(title="会穿 · AI 男性穿搭助手 API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

def get_base_url():
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN") \
          or os.environ.get("RAILWAY_STATIC_URL") \
          or "huichuan-production.up.railway.app"
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
    return f"https://{domain}"

@app.on_event("startup")
def startup():
    init_db()

app.include_router(recommend_router, prefix="/api")
app.include_router(products_router, prefix="/api")

@app.get("/")
def root():
    return {"status": "ok", "message": "会穿 API v2.0"}

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
    ext = "jpg" if file.content_type == "image/jpeg" else file.content_type.split("/")[1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(UPLOAD_DIR / filename, "wb") as f:
        f.write(content)
    return {"url": f"{get_base_url()}/uploads/{filename}"}
