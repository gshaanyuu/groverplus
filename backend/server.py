from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone, timedelta
import os, uuid, httpx, requests, logging

logger = logging.getLogger("grove")

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI()
api = APIRouter(prefix="/api")
SOCIETIES = ["Prestige Ozone", "Palm Meadows", "Brigade Gateway", "Sobha Dream Acres", "Godrej Woods"]
EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "grove-seller"
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024

_storage_key: Optional[str] = None


def init_storage(force: bool = False) -> str:
    global _storage_key
    if _storage_key and not force:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=120,
        )
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    if resp.status_code == 404:
        key = init_storage(force=True)
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")


class Seller(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None


class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    price: float
    stock: int = Field(ge=0)
    available: bool = True
    image_url: Optional[str] = None


class Customer(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: str
    address: str
    society: str


class OrderItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    price: float


class Order(BaseModel):
    id: str = Field(default_factory=lambda: "ORD-" + uuid.uuid4().hex[:6].upper())
    customer_id: str
    customer_name: str
    society: str
    items: List[OrderItem]
    total: float
    status: str = "Pending"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SessionRequest(BaseModel):
    session_id: str


async def get_current_seller(request: Request) -> Seller:
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    seller_doc = await db.sellers.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not seller_doc:
        raise HTTPException(status_code=401, detail="Seller not found")
    return Seller(**seller_doc)


@api.get("/")
async def root():
    return {"message": "Seller portal API"}


@api.post("/auth/session")
async def create_session(payload: SessionRequest, response: Response):
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": payload.session_id})
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session_id")
    data = r.json()
    email = data["email"]
    seller_doc = await db.sellers.find_one({"email": email}, {"_id": 0})
    if seller_doc:
        user_id = seller_doc["user_id"]
        await db.sellers.update_one({"user_id": user_id}, {"$set": {"name": data.get("name"), "picture": data.get("picture")}})
    else:
        user_id = f"seller_{uuid.uuid4().hex[:12]}"
        await db.sellers.insert_one({
            "user_id": user_id,
            "email": email,
            "name": data.get("name"),
            "picture": data.get("picture"),
            "created_at": datetime.now(timezone.utc),
        })
    session_token = data["session_token"]
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc),
    })
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )
    return {"user_id": user_id, "email": email, "name": data.get("name"), "picture": data.get("picture")}


@api.get("/auth/me", response_model=Seller)
async def me(seller: Seller = Depends(get_current_seller)):
    return seller


@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"success": True}


@api.get("/societies")
async def societies():
    return {"societies": SOCIETIES}


@api.get("/products", response_model=List[Product])
async def get_products(seller: Seller = Depends(get_current_seller)):
    return await db.products.find({}, {"_id": 0}).to_list(200)


@api.post("/products", response_model=Product)
async def create_product(product: Product, seller: Seller = Depends(get_current_seller)):
    data = product.model_dump()
    await db.products.insert_one(data)
    return product


@api.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product: Product, seller: Seller = Depends(get_current_seller)):
    data = product.model_dump()
    data["id"] = product_id
    result = await db.products.replace_one({"id": product_id}, data)
    if not result.matched_count:
        raise HTTPException(404, "Product not found")
    return Product(**data)


@api.delete("/products/{product_id}")
async def delete_product(product_id: str, seller: Seller = Depends(get_current_seller)):
    result = await db.products.delete_one({"id": product_id})
    if not result.deleted_count:
        raise HTTPException(404, "Product not found")
    return {"success": True}


@api.post("/upload/product-image")
async def upload_product_image(file: UploadFile = File(...), seller: Seller = Depends(get_current_seller)):
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Only JPEG, PNG, WEBP or GIF images are allowed")
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "Image is larger than 6 MB")
    ext = (file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else content_type.split("/")[-1]).lower()
    path = f"{APP_NAME}/products/{seller.user_id}/{uuid.uuid4()}.{ext}"
    try:
        result = put_object(path, data, content_type)
    except Exception as e:
        logger.exception("upload failed")
        raise HTTPException(502, f"Upload failed: {e}")
    stored_path = result["path"]
    await db.files.insert_one({
        "id": str(uuid.uuid4()),
        "storage_path": stored_path,
        "original_filename": file.filename,
        "content_type": content_type,
        "size": result.get("size", len(data)),
        "uploaded_by": seller.user_id,
        "is_deleted": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"path": stored_path, "url": f"/api/files/{stored_path}"}


@api.get("/files/{path:path}")
async def serve_file(path: str, seller: Seller = Depends(get_current_seller)):
    record = await db.files.find_one({"storage_path": path, "is_deleted": False}, {"_id": 0})
    if not record:
        raise HTTPException(404, "File not found")
    try:
        data, content_type = get_object(path)
    except Exception as e:
        logger.exception("file fetch failed")
        raise HTTPException(502, f"File fetch failed: {e}")
    return Response(content=data, media_type=record.get("content_type") or content_type, headers={"Cache-Control": "private, max-age=3600"})


@api.get("/customers", response_model=List[Customer])
async def get_customers(seller: Seller = Depends(get_current_seller)):
    return await db.customers.find({}, {"_id": 0}).to_list(200)


@api.post("/customers", response_model=Customer)
async def create_customer(customer: Customer, seller: Seller = Depends(get_current_seller)):
    if customer.society not in SOCIETIES:
        raise HTTPException(400, "Choose a listed society")
    data = customer.model_dump()
    await db.customers.insert_one(data)
    return customer


@api.put("/customers/{customer_id}", response_model=Customer)
async def update_customer(customer_id: str, customer: Customer, seller: Seller = Depends(get_current_seller)):
    if customer.society not in SOCIETIES:
        raise HTTPException(400, "Choose a listed society")
    data = customer.model_dump()
    data["id"] = customer_id
    result = await db.customers.replace_one({"id": customer_id}, data)
    if not result.matched_count:
        raise HTTPException(404, "Customer not found")
    return Customer(**data)


@api.delete("/customers/{customer_id}")
async def delete_customer(customer_id: str, seller: Seller = Depends(get_current_seller)):
    result = await db.customers.delete_one({"id": customer_id})
    if not result.deleted_count:
        raise HTTPException(404, "Customer not found")
    return {"success": True}


@api.get("/orders", response_model=List[Order])
async def get_orders(seller: Seller = Depends(get_current_seller)):
    return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)


@api.get("/insights/societies")
async def society_insights(seller: Seller = Depends(get_current_seller)):
    now = datetime.now(timezone.utc)
    week_start = (now - timedelta(days=7)).isoformat()
    prev_start = (now - timedelta(days=14)).isoformat()
    orders = await db.orders.find({"created_at": {"$gte": prev_start}}, {"_id": 0}).to_list(1000)
    agg = {s: {"society": s, "orders_this_week": 0, "revenue_this_week": 0.0, "orders_prev_week": 0, "revenue_prev_week": 0.0, "product_counts": {}} for s in SOCIETIES}
    for o in orders:
        if o.get("society") not in agg:
            continue
        bucket = agg[o["society"]]
        if o["created_at"] >= week_start:
            bucket["orders_this_week"] += 1
            bucket["revenue_this_week"] += float(o.get("total", 0))
            for it in o.get("items", []):
                bucket["product_counts"][it["name"]] = bucket["product_counts"].get(it["name"], 0) + int(it.get("quantity", 0))
        else:
            bucket["orders_prev_week"] += 1
            bucket["revenue_prev_week"] += float(o.get("total", 0))
    result = []
    for s in SOCIETIES:
        b = agg[s]
        top = max(b["product_counts"].items(), key=lambda kv: kv[1], default=(None, 0))
        prev = b["revenue_prev_week"]
        change_pct = None if prev == 0 else round((b["revenue_this_week"] - prev) / prev * 100, 1)
        result.append({
            "society": s,
            "orders_this_week": b["orders_this_week"],
            "revenue_this_week": round(b["revenue_this_week"], 2),
            "revenue_prev_week": round(prev, 2),
            "change_pct": change_pct,
            "top_product": top[0],
            "top_product_qty": top[1],
        })
    result.sort(key=lambda r: r["revenue_this_week"], reverse=True)
    total_revenue = round(sum(r["revenue_this_week"] for r in result), 2)
    return {"week_start": week_start, "total_revenue": total_revenue, "societies": result}


@api.post("/orders", response_model=Order)
async def create_order(order: Order, seller: Seller = Depends(get_current_seller)):
    for item in order.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product or item.quantity > product["stock"]:
            raise HTTPException(400, f"Not enough stock for {item.name}")
    data = order.model_dump()
    await db.orders.insert_one(data)
    for item in order.items:
        await db.products.update_one({"id": item.product_id}, {"$inc": {"stock": -item.quantity}})
    return order


@api.patch("/orders/{order_id}/status", response_model=Order)
async def update_status(order_id: str, status: str, seller: Seller = Depends(get_current_seller)):
    if status not in {"Pending", "Out for Delivery", "Delivered"}:
        raise HTTPException(400, "Invalid delivery status")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": status}})
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Order not found")
    return Order(**order)


@app.on_event("startup")
async def seed_data():
    try:
        init_storage()
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")
    if await db.products.count_documents({}) == 0:
        await db.products.insert_many([
            Product(name="Farm Fresh Milk", category="Dairy", price=58, stock=34).model_dump(),
            Product(name="Organic Bananas", category="Produce", price=72, stock=12).model_dump(),
            Product(name="Sourdough Loaf", category="Bakery", price=145, stock=8).model_dump(),
            Product(name="Free Range Eggs", category="Dairy", price=110, stock=24).model_dump(),
        ])
    if await db.customers.count_documents({}) == 0:
        await db.customers.insert_many([
            Customer(name="Riya Menon", phone="9876543210", address="Tower A, 302", society="Palm Meadows").model_dump(),
            Customer(name="Kabir Rao", phone="9988776655", address="Villa 18", society="Prestige Ozone").model_dump(),
            Customer(name="Meera Iyer", phone="9123456780", address="Block C, 1104", society="Brigade Gateway").model_dump(),
        ])


app.include_router(api)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ["CORS_ORIGINS"].split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown():
    client.close()
