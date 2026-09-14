from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from pathlib import Path
from typing import List, Optional
from datetime import datetime, timezone
import os, uuid, random

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")
client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]
app = FastAPI()
api = APIRouter(prefix="/api")
SOCIETIES = ["Prestige Ozone", "Palm Meadows", "Brigade Gateway", "Sobha Dream Acres", "Godrej Woods"]
otp_store = {}

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    price: float
    stock: int
    available: bool = True

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
    id: str = Field(default_factory=lambda: "ORD-" + str(random.randint(1000, 9999)))
    customer_id: str
    customer_name: str
    society: str
    items: List[OrderItem]
    total: float
    status: str = "Pending"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class OtpRequest(BaseModel): phone: str
class OtpVerify(BaseModel): phone: str; otp: str

@api.get("/")
async def root(): return {"message": "Seller portal API"}

@api.post("/auth/request-otp")
async def request_otp(payload: OtpRequest):
    otp_store[payload.phone] = "123456"
    return {"success": True, "message": "Demo OTP sent", "demo_otp": "123456"}

@api.post("/auth/verify-otp")
async def verify_otp(payload: OtpVerify):
    if otp_store.get(payload.phone) != payload.otp: raise HTTPException(400, "Invalid OTP. Use 123456 for this demo.")
    return {"success": True, "seller": {"name": "Ananya Sharma", "phone": payload.phone}, "session": "demo-seller-session"}

@api.get("/societies")
async def societies(): return {"societies": SOCIETIES}

@api.get("/products", response_model=List[Product])
async def get_products(): return await db.products.find({}, {"_id": 0}).to_list(200)

@api.post("/products", response_model=Product)
async def create_product(product: Product):
    data = product.model_dump(); await db.products.insert_one(data); return product

@api.put("/products/{product_id}", response_model=Product)
async def update_product(product_id: str, product: Product):
    data = product.model_dump(); data["id"] = product_id
    result = await db.products.replace_one({"id": product_id}, data)
    if not result.matched_count: raise HTTPException(404, "Product not found")
    return Product(**data)

@api.get("/customers", response_model=List[Customer])
async def get_customers(): return await db.customers.find({}, {"_id": 0}).to_list(200)

@api.post("/customers", response_model=Customer)
async def create_customer(customer: Customer):
    if customer.society not in SOCIETIES: raise HTTPException(400, "Choose a listed society")
    data = customer.model_dump(); await db.customers.insert_one(data); return customer

@api.put("/customers/{customer_id}", response_model=Customer)
async def update_customer(customer_id: str, customer: Customer):
    if customer.society not in SOCIETIES: raise HTTPException(400, "Choose a listed society")
    data = customer.model_dump(); data["id"] = customer_id
    result = await db.customers.replace_one({"id": customer_id}, data)
    if not result.matched_count: raise HTTPException(404, "Customer not found")
    return Customer(**data)

@api.get("/orders", response_model=List[Order])
async def get_orders(): return await db.orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)

@api.post("/orders", response_model=Order)
async def create_order(order: Order):
    for item in order.items:
        product = await db.products.find_one({"id": item.product_id}, {"_id": 0})
        if not product or item.quantity > product["stock"]: raise HTTPException(400, f"Not enough stock for {item.name}")
    data = order.model_dump(); await db.orders.insert_one(data)
    for item in order.items: await db.products.update_one({"id": item.product_id}, {"$inc": {"stock": -item.quantity}})
    return order

@api.patch("/orders/{order_id}/status", response_model=Order)
async def update_status(order_id: str, status: str):
    if status not in {"Pending", "Out for Delivery", "Delivered"}: raise HTTPException(400, "Invalid delivery status")
    await db.orders.update_one({"id": order_id}, {"$set": {"status": status}})
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order: raise HTTPException(404, "Order not found")
    return Order(**order)

@app.on_event("startup")
async def seed_data():
    if await db.products.count_documents({}) == 0:
        await db.products.insert_many([Product(name="Farm Fresh Milk", category="Dairy", price=58, stock=34).model_dump(), Product(name="Organic Bananas", category="Produce", price=72, stock=12).model_dump(), Product(name="Sourdough Loaf", category="Bakery", price=145, stock=8).model_dump(), Product(name="Free Range Eggs", category="Dairy", price=110, stock=24).model_dump()])
    if await db.customers.count_documents({}) == 0:
        await db.customers.insert_many([Customer(name="Riya Menon", phone="9876543210", address="Tower A, 302", society="Palm Meadows").model_dump(), Customer(name="Kabir Rao", phone="9988776655", address="Villa 18", society="Prestige Ozone").model_dump(), Customer(name="Meera Iyer", phone="9123456780", address="Block C, 1104", society="Brigade Gateway").model_dump()])

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","), allow_methods=["*"], allow_headers=["*"])
@app.on_event("shutdown")
async def shutdown(): client.close()