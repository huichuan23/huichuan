"""
商品 API 路由
GET  /api/products          搜索商品
GET  /api/products/stats    数据库统计
POST /api/products/import   从 products.json 导入数据
"""
from fastapi import APIRouter, Depends, Query, BackgroundTasks, Header, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
import json
from pathlib import Path

from database import get_db, Product, ScrapeLog
from datetime import datetime

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY")


def require_admin(x_admin_key: Optional[str] = Header(default=None)):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API is disabled")
    if x_admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def get_import_json_path() -> Path:
    candidates = [
        PROJECT_ROOT / "frontend" / "products.json",
        PROJECT_ROOT / "backend" / "data" / "products.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise HTTPException(status_code=404, detail="products.json not found")


@router.get("/products")
def search_products(
    category: Optional[str] = Query(None),
    brand:    Optional[str] = Query(None),
    max_price: Optional[float] = Query(None),
    min_price: Optional[float] = Query(None),
    color_tone: Optional[str] = Query(None),
    tags:     Optional[str] = Query(None),  # 逗号分隔
    limit:    int = Query(20, le=100),
    offset:   int = Query(0),
    db: Session = Depends(get_db)
):
    q = db.query(Product)

    if category:
        q = q.filter(Product.category == category)
    if brand:
        q = q.filter(Product.brand == brand)
    if max_price is not None:
        q = q.filter(Product.price <= max_price)
    if min_price is not None:
        q = q.filter(Product.price >= min_price)
    if color_tone:
        q = q.filter(Product.color_tone == color_tone)

    total = q.count()
    products = q.offset(offset).limit(limit).all()

    return {
        "total": total,
        "products": [
            {
                "id":         p.id,
                "source":     p.source,
                "category":   p.category,
                "name":       p.name,
                "brand":      p.brand,
                "price":      p.price,
                "currency":   p.currency,
                "color":      p.color,
                "color_tone": p.color_tone,
                "img":        p.img,
                "buy":        p.buy,
                "tags":       p.tags,
                "avoid_body": p.avoid_body,
            }
            for p in products
        ]
    }


@router.get("/products/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(Product.id)).scalar()
    by_category = db.query(Product.category, func.count(Product.id))\
        .group_by(Product.category).all()
    by_brand = db.query(Product.brand, func.count(Product.id))\
        .group_by(Product.brand).order_by(func.count(Product.id).desc()).all()
    by_source = db.query(Product.source, func.count(Product.id))\
        .group_by(Product.source).all()

    return {
        "total": total,
        "by_category": {cat: cnt for cat, cnt in by_category},
        "by_brand": {brand: cnt for brand, cnt in by_brand[:10]},
        "by_source": {src: cnt for src, cnt in by_source},
    }


@router.post("/products/import")
def import_products(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin)
):
    """从 products.json 文件导入数据到 PostgreSQL"""
    json_path = get_import_json_path()

    log = ScrapeLog(source="import", status="running")
    db.add(log); db.commit(); db.refresh(log)

    background_tasks.add_task(do_import, str(json_path), log.id)
    return {"message": "导入任务已启动", "log_id": log.id}


def do_import(json_path: str, log_id: int):
    from database import SessionLocal
    db = SessionLocal()
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        products = data.get("products", [])
        count = 0
        for p in products:
            existing = db.query(Product).filter(Product.id == p["id"]).first()
            # 判断颜色深浅
            color_tone = guess_color_tone(p.get("color_en", ""))

            product_data = {
                "id":         p["id"],
                "source":     p.get("source", "unknown"),
                "category":   p.get("category", "top"),
                "name":       p.get("name", ""),
                "brand":      p.get("brand", ""),
                "price":      float(p.get("price", 0)),
                "currency":   p.get("currency", "CAD"),
                "color":      p.get("color", ""),
                "color_en":   p.get("color_en", ""),
                "color_tone": color_tone,
                "img":        p.get("img", ""),
                "buy":        p.get("buy", ""),
                "tags":       p.get("tags", []),
                "avoid_body": p.get("avoid_body", []),
                "season":     p.get("season", []),
                "fit":        p.get("fit", "regular"),
                "updated_at": datetime.utcnow(),
            }

            if existing:
                for k, v in product_data.items():
                    setattr(existing, k, v)
            else:
                db.add(Product(**product_data))
            count += 1

        db.commit()

        log = db.query(ScrapeLog).filter(ScrapeLog.id == log_id).first()
        log.status = "success"
        log.total = count
        log.message = f"成功导入 {count} 件商品"
        log.finished_at = datetime.utcnow()
        db.commit()
        print(f"✅ 导入完成：{count} 件商品")

    except Exception as e:
        log = db.query(ScrapeLog).filter(ScrapeLog.id == log_id).first()
        log.status = "failed"
        log.message = str(e)
        log.finished_at = datetime.utcnow()
        db.commit()
        print(f"❌ 导入失败：{e}")
    finally:
        db.close()


def guess_color_tone(color_en: str) -> str:
    c = color_en.lower()
    light_colors = ["white","off white","cream","ivory","beige","light","yellow","pink","light blue","light gray","light grey","mint","lavender"]
    dark_colors  = ["black","dark","navy","charcoal","burgundy","wine","dark green","dark brown","dark gray","dark grey","deep"]
    for lc in light_colors:
        if lc in c: return "light"
    for dc in dark_colors:
        if dc in c: return "dark"
    return "medium"
