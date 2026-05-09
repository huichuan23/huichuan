"""
优衣库加拿大商品爬虫 v5
使用真实图片 URL 格式：cagoods_[colorCode]_[productId]_3x4.jpg
"""

import json, time, os
from playwright.sync_api import sync_playwright

CATEGORIES = [
    ("men_tshirts",     "https://www.uniqlo.com/ca/en/men/tops",                                           "top"),
    ("men_sweatshirts", "https://www.uniqlo.com/ca/en/men/tops/sweatshirts-and-hoodies?path=%2C%2C574%2C", "top"),
    ("men_polo",        "https://www.uniqlo.com/ca/en/men/shirts-and-polo-shirts/polo-shirts",             "top"),
    ("men_shirts",      "https://www.uniqlo.com/ca/en/men/tops/shirts",                                    "top"),
    ("men_sweaters",    "https://www.uniqlo.com/ca/en/men/sweaters-and-knitwear",                          "top"),
    ("men_outerwear",   "https://www.uniqlo.com/ca/en/men/outerwear",                                      "top"),
    ("men_bottoms",     "https://www.uniqlo.com/ca/en/men/bottoms",                                        "bottom"),
    ("men_shorts",      "https://www.uniqlo.com/ca/en/men/bottoms/shorts?path=%2C%2C41402%2C",             "bottom"),
]

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../frontend/products.json")
IMG_DIR     = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../frontend/images")

COLOR_MAP = {
    "white":"白色","off white":"米白","off-white":"米白","cream":"米白","ivory":"米白",
    "black":"黑色","charcoal":"深灰","dark gray":"深灰","dark grey":"深灰",
    "gray":"灰色","grey":"灰色","light gray":"浅灰","light grey":"浅灰","heather":"浅灰",
    "navy":"藏蓝","blue":"蓝色","light blue":"浅蓝",
    "khaki":"卡其","beige":"米色","tan":"棕褐","camel":"驼色",
    "brown":"棕色","green":"绿色","olive":"橄榄绿",
    "red":"红色","burgundy":"酒红","pink":"粉色",
    "yellow":"黄色","orange":"橙色","purple":"紫色",
    "stripe":"条纹","check":"格纹","plaid":"格子",
}

def to_zh(c):
    c = c.lower().strip()
    for en, zh in COLOR_MAP.items():
        if en in c: return zh
    return c

def auto_tag(name, color, cat_type):
    n = name.lower()
    tags = ["basic","clean"]
    if cat_type == "top":
        if "polo" in n: tags += ["smart_casual","korean","preppy","business_casual"]
        elif "shirt" in n and "t-shirt" not in n: tags += ["smart_casual","korean","formal","business_casual","preppy"]
        elif any(w in n for w in ["sweatshirt","hoodie","fleece","pullover","sweater","knit"]): tags += ["casual","street","american"]
        elif any(w in n for w in ["coat","jacket","parka","blouson","puffer","down"]): tags += ["casual","smart_casual","american"]
        else: tags += ["casual","minimal","simple"]
    else:
        if any(w in n for w in ["jean","denim"]): tags += ["casual","korean","street","american"]
        elif "short" in n: tags += ["casual","sport","simple"]
        elif any(w in n for w in ["slim","skinny","tapered"]): tags += ["korean","smart_casual"]
        elif any(w in n for w in ["wide","relaxed","loose"]): tags += ["street","american","casual"]
        else: tags += ["smart_casual","preppy","business_casual","minimal"]
    if any(s in color.lower() for s in ["white","black","grey","gray","navy","khaki","beige","cream"]):
        tags.append("minimal")
    return list(set(tags))

def get_avoid(name):
    n = name.lower()
    avoid = []
    if any(w in n for w in ["slim","skinny","fitted"]): avoid.append("偏胖")
    if any(w in n for w in ["oversized","wide","relaxed","loose"]): avoid.append("偏瘦")
    return avoid

def scrape():
    all_products = []
    seen_ids = set()
    os.makedirs(IMG_DIR, exist_ok=True)

    with sync_playwright() as p:
        print("启动浏览器...")
        browser = p.chromium.launch(headless=False, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            viewport={"width":1280,"height":800}, locale="en-CA",
        )
        page = context.new_page()
        captured = []

        def on_response(response):
            if "/api/commerce/v5/en/products" in response.url and response.status == 200:
                try:
                    data = response.json()
                    if data.get("status") == "ok":
                        items = data.get("result",{}).get("items",[])
                        if items:
                            captured.append(data)
                            print(f"    → 捕获 {len(items)} 件商品")
                except: pass

        page.on("response", on_response)

        for cat_name, cat_url, cat_type in CATEGORIES:
            print(f"\n[{cat_name}] 访问：{cat_url}")
            captured.clear()

            try:
                page.goto(cat_url, timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                for _ in range(4):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(1200)

                for api_data in captured:
                    items = api_data.get("result",{}).get("items",[])
                    for item in items:
                        pid = item.get("productId","")
                        if not pid or pid in seen_ids: continue
                        seen_ids.add(pid)

                        name      = item.get("name","")
                        price     = item.get("prices",{}).get("base",{}).get("value", 0)
                        colors    = item.get("colors",[])
                        color_obj = colors[0] if colors else {}
                        color_code = color_obj.get("displayCode","00")
                        color_en   = color_obj.get("name","White")

                        # 从 API 直接获取真实图片 URL
                        images = item.get("images",{})
                        main_imgs = images.get("main",{})
                        # main 是 {colorCode: {image: url, model: [...]}} 结构
                        img_url = None
                        if color_code in main_imgs:
                            img_url = main_imgs[color_code].get("image","")
                        elif main_imgs:
                            first_key = list(main_imgs.keys())[0]
                            img_url = main_imgs[first_key].get("image","")

                        if not img_url:
                            # fallback
                            img_url = f"https://image.uniqlo.com/UQ/ST3/ca/imagesgoods/{pid}/item/cagoods_{color_code}_{pid}_3x4.jpg"

                        # 下载图片
                        img_fname = f"uq_{pid}_{color_code}.jpg"
                        img_local = os.path.join(IMG_DIR, img_fname)
                        print(f"  图片：{name[:35]}...", end=" ")
                        try:
                            resp = page.request.get(img_url, headers={
                                "Referer": cat_url,
                                "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
                            })
                            if resp.ok:
                                with open(img_local,"wb") as f:
                                    f.write(resp.body())
                                img_path = f"images/{img_fname}"
                                print("✓")
                            else:
                                img_path = img_url
                                print(f"✗ ({resp.status})")
                        except Exception as e:
                            img_path = img_url
                            print(f"✗ ({e})")

                        all_products.append({
                            "id":         f"uq_{pid}_{color_code}",
                            "source":     "uniqlo_ca",
                            "category":   cat_type,
                            "name":       f"UNIQLO {name}",
                            "brand":      "UNIQLO",
                            "price":      price,
                            "currency":   "CAD",
                            "color":      to_zh(color_en),
                            "color_en":   color_en,
                            "img":        img_path,
                            "buy":        f"https://www.uniqlo.com/ca/en/products/{pid}-000/00",
                            "tags":       auto_tag(name, color_en, cat_type),
                            "avoid_body": get_avoid(name),
                        })

                tops    = len([p for p in all_products if p["category"]=="top"])
                bottoms = len([p for p in all_products if p["category"]=="bottom"])
                print(f"  累计：上衣 {tops}，裤子 {bottoms}")

            except Exception as e:
                print(f"  ✗ 错误：{e}")

        browser.close()
    return all_products

if __name__ == "__main__":
    print("=" * 55)
    print("优衣库加拿大商品爬虫 v5")
    print("=" * 55)

    products = scrape()
    tops    = len([p for p in products if p["category"]=="top"])
    bottoms = len([p for p in products if p["category"]=="bottom"])
    print(f"\n完成：上衣 {tops}，裤子 {bottoms}")

    if not products:
        print("未抓取到商品"); exit(1)

    output = {"source":"uniqlo_ca","scraped_at":time.strftime("%Y-%m-%d"),"products":products}
    with open(OUTPUT_FILE,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    img_count = len([f for f in os.listdir(IMG_DIR) if f.endswith(".jpg")])
    print(f"\n✅ products.json 已保存")
    print(f"   成功下载图片：{img_count} 张")
    print(f"\n接下来运行这4条命令推到 GitHub：")
    print(f"  copy frontend\\products.json products.json")
    print(f"  xcopy frontend\\images images\\ /E /I /Y")
    print(f"  git add products.json images\\")
    print(f"  git commit -m \"add images v5\"")
    print(f"  git push origin master --force")
