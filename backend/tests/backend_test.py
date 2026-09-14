"""Regression tests for the Seller Portal API using Emergent Google OAuth session tokens.

Seeds a test seller + user_session directly in Mongo, then exercises all /api endpoints
using Authorization: Bearer <session_token>.
"""
import os
import time
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv


load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

SOCIETIES = ["Prestige Ozone", "Palm Meadows", "Brigade Gateway", "Sobha Dream Acres", "Godrej Woods"]


# ---------- Fixtures ----------
@pytest.fixture(scope="session")
def mongo_db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="session")
def seeded_session(mongo_db):
    """Seed a seller + user_session directly and return the bearer token + user."""
    user_id = f"test-user-{uuid.uuid4().hex[:10]}"
    token = f"test_session_{uuid.uuid4().hex}"
    email = f"seller.qa.{int(time.time())}@example.com"
    mongo_db.sellers.insert_one({
        "user_id": user_id,
        "email": email,
        "name": "QA Seller",
        "picture": "https://via.placeholder.com/150",
        "created_at": datetime.now(timezone.utc),
    })
    mongo_db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": user_id, "token": token, "email": email}
    # cleanup
    mongo_db.user_sessions.delete_many({"user_id": user_id})
    mongo_db.sellers.delete_many({"user_id": user_id})


@pytest.fixture
def client():
    with requests.Session() as s:
        yield s


@pytest.fixture
def auth_client(seeded_session):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {seeded_session['token']}"})
    yield s
    s.close()


# ---------- Unauthenticated tests ----------
class TestAuthGate:
    @pytest.mark.parametrize("path", ["/api/auth/me", "/api/products", "/api/customers", "/api/orders"])
    def test_unauthenticated_returns_401(self, client, path):
        r = client.get(f"{BASE_URL}{path}")
        assert r.status_code == 401

    def test_invalid_session_id_rejected(self, client):
        r = client.post(f"{BASE_URL}/api/auth/session", json={"session_id": "bogus-invalid-session-id"})
        assert r.status_code == 401


# ---------- Auth /me and logout ----------
class TestAuthFlow:
    def test_me_returns_seller(self, auth_client, seeded_session):
        r = auth_client.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200
        data = r.json()
        assert data["user_id"] == seeded_session["user_id"]
        assert data["email"] == seeded_session["email"]
        assert data["name"] == "QA Seller"

    def test_logout_invalidates_session(self, mongo_db):
        # Create a dedicated session for logout so we don't disrupt other tests
        user_id = f"test-user-{uuid.uuid4().hex[:10]}"
        token = f"test_session_{uuid.uuid4().hex}"
        mongo_db.sellers.insert_one({
            "user_id": user_id, "email": f"logout.{uuid.uuid4().hex[:6]}@x.com",
            "name": "Logout QA", "created_at": datetime.now(timezone.utc),
        })
        mongo_db.user_sessions.insert_one({
            "user_id": user_id, "session_token": token,
            "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
            "created_at": datetime.now(timezone.utc),
        })
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {token}"
        me = s.get(f"{BASE_URL}/api/auth/me")
        assert me.status_code == 200

        out = s.post(f"{BASE_URL}/api/auth/logout")
        assert out.status_code == 200

        after = s.get(f"{BASE_URL}/api/auth/me")
        assert after.status_code == 401
        mongo_db.sellers.delete_many({"user_id": user_id})


# ---------- Products ----------
class TestProducts:
    def test_get_products_returns_seeded(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/products")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        assert "_id" not in data[0] and "id" in data[0]

    def test_create_update_and_reject_negative_stock(self, auth_client):
        create = auth_client.post(f"{BASE_URL}/api/products", json={
            "name": "TEST_Product", "category": "Pantry", "price": 100, "stock": 10, "available": True,
        })
        assert create.status_code == 200
        pid = create.json()["id"]

        upd = auth_client.put(f"{BASE_URL}/api/products/{pid}", json={
            "name": "TEST_Product", "category": "Pantry", "price": 120, "stock": 5, "available": False,
        })
        assert upd.status_code == 200
        assert upd.json()["price"] == 120 and upd.json()["stock"] == 5

        neg = auth_client.put(f"{BASE_URL}/api/products/{pid}", json={
            "name": "TEST_Product", "category": "Pantry", "price": 120, "stock": -1, "available": True,
        })
        assert neg.status_code == 422

        # Confirm stock still 5
        fetched = next(p for p in auth_client.get(f"{BASE_URL}/api/products").json() if p["id"] == pid)
        assert fetched["stock"] == 5


# ---------- Customers ----------
class TestCustomers:
    def test_reject_unknown_society_on_create(self, auth_client):
        r = auth_client.post(f"{BASE_URL}/api/customers", json={
            "name": "TEST_Cust1", "phone": "9000011111", "address": "Addr", "society": "Not Real",
        })
        assert r.status_code == 400

    def test_create_and_update_customer(self, auth_client):
        r = auth_client.post(f"{BASE_URL}/api/customers", json={
            "name": "TEST_Cust2", "phone": "9000022222", "address": "Old", "society": "Palm Meadows",
        })
        assert r.status_code == 200
        cid = r.json()["id"]
        upd = auth_client.put(f"{BASE_URL}/api/customers/{cid}", json={
            "name": "TEST_Cust2 Updated", "phone": "9000022222", "address": "New Addr", "society": "Godrej Woods",
        })
        assert upd.status_code == 200
        assert upd.json()["society"] == "Godrej Woods" and upd.json()["name"] == "TEST_Cust2 Updated"


# ---------- Orders ----------
class TestOrders:
    def test_order_decrements_stock_and_rejects_overshoot(self, auth_client):
        # Create fresh product with stock 3
        prod = auth_client.post(f"{BASE_URL}/api/products", json={
            "name": "TEST_OrderProd", "category": "Pantry", "price": 50, "stock": 3, "available": True,
        }).json()
        cust = auth_client.post(f"{BASE_URL}/api/customers", json={
            "name": "TEST_OrderCust", "phone": "9000033333", "address": "A", "society": "Palm Meadows",
        }).json()

        # Overshoot: request 5 units
        over = auth_client.post(f"{BASE_URL}/api/orders", json={
            "customer_id": cust["id"], "customer_name": cust["name"], "society": cust["society"],
            "items": [{"product_id": prod["id"], "name": prod["name"], "quantity": 5, "price": prod["price"]}],
            "total": 250,
        })
        assert over.status_code == 400

        # Valid order: 2 units, stock should go 3->1
        ok = auth_client.post(f"{BASE_URL}/api/orders", json={
            "customer_id": cust["id"], "customer_name": cust["name"], "society": cust["society"],
            "items": [{"product_id": prod["id"], "name": prod["name"], "quantity": 2, "price": prod["price"]}],
            "total": 100,
        })
        assert ok.status_code == 200
        order_id = ok.json()["id"]

        fetched = next(p for p in auth_client.get(f"{BASE_URL}/api/products").json() if p["id"] == prod["id"])
        assert fetched["stock"] == 1

        # Status transitions
        for status in ["Out for Delivery", "Delivered"]:
            r = auth_client.patch(f"{BASE_URL}/api/orders/{order_id}/status", params={"status": status})
            assert r.status_code == 200
            assert r.json()["status"] == status

        # Invalid status
        bad = auth_client.patch(f"{BASE_URL}/api/orders/{order_id}/status", params={"status": "Cancelled"})
        assert bad.status_code == 400


# ---------- Societies list ----------
def test_societies_list(auth_client):
    r = auth_client.get(f"{BASE_URL}/api/societies")
    assert r.status_code == 200
    assert r.json()["societies"] == SOCIETIES
