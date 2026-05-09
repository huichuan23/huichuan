from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
