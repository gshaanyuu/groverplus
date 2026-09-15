"""Tests for iteration 7 features: product photo upload, product/customer delete, image_url persistence."""
import base64
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

# 1x1 PNG
PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture(scope="module")
def mongo_db():
    c = MongoClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def seeded(mongo_db):
    user_id = f"test-user-{uuid.uuid4().hex[:10]}"
    token = f"test_session_{uuid.uuid4().hex}"
    mongo_db.sellers.insert_one({
        "user_id": user_id, "email": f"newfeat.{int(time.time())}@example.com",
        "name": "NewFeat QA", "created_at": datetime.now(timezone.utc),
    })
    mongo_db.user_sessions.insert_one({
        "user_id": user_id, "session_token": token,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=1),
        "created_at": datetime.now(timezone.utc),
    })
    yield {"user_id": user_id, "token": token}
    mongo_db.user_sessions.delete_many({"user_id": user_id})
    mongo_db.sellers.delete_many({"user_id": user_id})


@pytest.fixture
def auth(seeded):
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {seeded['token']}"
    yield s
    s.close()


# ---------- Upload ----------
class TestUpload:
    def test_upload_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/upload/product-image",
            files={"file": ("a.png", PNG_BYTES, "image/png")},
        )
        assert r.status_code == 401

    def test_upload_rejects_non_image(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/upload/product-image",
            files={"file": ("a.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert r.status_code == 400

    def test_upload_png_and_fetch(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/upload/product-image",
            files={"file": ("t.png", PNG_BYTES, "image/png")},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "path" in body and "url" in body
        assert body["url"] == f"/api/files/{body['path']}"

        # Fetch back
        g = auth.get(f"{BASE_URL}{body['url']}")
        assert g.status_code == 200
        assert g.headers.get("content-type", "").startswith("image/")
        assert g.content == PNG_BYTES

    def test_serve_unauth(self, auth):
        r = auth.post(
            f"{BASE_URL}/api/upload/product-image",
            files={"file": ("t.png", PNG_BYTES, "image/png")},
        )
        assert r.status_code == 200
        path = r.json()["path"]
        anon = requests.get(f"{BASE_URL}/api/files/{path}")
        assert anon.status_code == 401


# ---------- Product image_url persistence ----------
class TestProductImageUrl:
    def test_create_and_update_image_url(self, auth):
        create = auth.post(f"{BASE_URL}/api/products", json={
            "name": "TEST_PhotoProd", "category": "Pantry", "price": 100, "stock": 5,
            "available": True, "image_url": "/api/files/some/path.png",
        })
        assert create.status_code == 200
        pid = create.json()["id"]
        assert create.json()["image_url"] == "/api/files/some/path.png"

        listed = next(p for p in auth.get(f"{BASE_URL}/api/products").json() if p["id"] == pid)
        assert listed["image_url"] == "/api/files/some/path.png"

        upd = auth.put(f"{BASE_URL}/api/products/{pid}", json={
            "name": "TEST_PhotoProd", "category": "Pantry", "price": 100, "stock": 5,
            "available": True, "image_url": "/api/files/other.png",
        })
        assert upd.status_code == 200
        assert upd.json()["image_url"] == "/api/files/other.png"


# ---------- Product delete ----------
class TestProductDelete:
    def test_delete_unauth(self):
        r = requests.delete(f"{BASE_URL}/api/products/anything")
        assert r.status_code == 401

    def test_delete_not_found(self, auth):
        r = auth.delete(f"{BASE_URL}/api/products/does-not-exist-xyz")
        assert r.status_code == 404

    def test_delete_success(self, auth):
        c = auth.post(f"{BASE_URL}/api/products", json={
            "name": "TEST_DelProd", "category": "Pantry", "price": 10, "stock": 1, "available": True,
        })
        pid = c.json()["id"]
        d = auth.delete(f"{BASE_URL}/api/products/{pid}")
        assert d.status_code == 200
        assert d.json() == {"success": True}
        assert all(p["id"] != pid for p in auth.get(f"{BASE_URL}/api/products").json())


# ---------- Customer delete ----------
class TestCustomerDelete:
    def test_delete_unauth(self):
        r = requests.delete(f"{BASE_URL}/api/customers/anything")
        assert r.status_code == 401

    def test_delete_not_found(self, auth):
        r = auth.delete(f"{BASE_URL}/api/customers/does-not-exist-xyz")
        assert r.status_code == 404

    def test_delete_success(self, auth):
        c = auth.post(f"{BASE_URL}/api/customers", json={
            "name": "TEST_DelCust", "phone": "9000099999", "address": "A", "society": "Palm Meadows",
        })
        cid = c.json()["id"]
        d = auth.delete(f"{BASE_URL}/api/customers/{cid}")
        assert d.status_code == 200
        assert d.json() == {"success": True}
        assert all(x["id"] != cid for x in auth.get(f"{BASE_URL}/api/customers").json())
