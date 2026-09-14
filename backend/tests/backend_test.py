"""Regression checks for seller authentication and seller portal read APIs."""
import os

import pytest
import requests


BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


@pytest.fixture
def client():
    with requests.Session() as session:
        yield session


def test_request_and_verify_demo_otp(client):
    phone = "9876543210"
    request = client.post(f"{BASE_URL}/api/auth/request-otp", json={"phone": phone})
    assert request.status_code == 200
    assert request.json()["demo_otp"] == "123456"
    verify = client.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": phone, "otp": "123456"})
    assert verify.status_code == 200
    assert verify.json()["seller"]["phone"] == phone


def test_invalid_otp_is_rejected(client):
    client.post(f"{BASE_URL}/api/auth/request-otp", json={"phone": "9876543211"})
    response = client.post(f"{BASE_URL}/api/auth/verify-otp", json={"phone": "9876543211", "otp": "000000"})
    assert response.status_code == 400
    assert "Invalid OTP" in response.json()["detail"]


@pytest.mark.parametrize("path,key", [("/api/products", "id"), ("/api/customers", "id"), ("/api/orders", "id")])
def test_seller_lists_are_available_without_mongodb_ids(client, path, key):
    response = client.get(f"{BASE_URL}{path}")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    if response.json():
        assert key in response.json()[0]
        assert "_id" not in response.json()[0]


def test_societies_returns_fixed_list(client):
    response = client.get(f"{BASE_URL}/api/societies")
    assert response.status_code == 200
    assert response.json()["societies"] == [
        "Prestige Ozone", "Palm Meadows", "Brigade Gateway", "Sobha Dream Acres", "Godrej Woods"
    ]


# Product/customer update persistence and order/status validation regression checks.
def test_product_update_persists_stock_price_and_availability(client):
    product = client.post(f"{BASE_URL}/api/products", json={
        "name": "TEST Update Product", "category": "Pantry", "price": 10,
        "stock": 5, "available": True,
    })
    assert product.status_code == 200
    product_id = product.json()["id"]
    update = client.put(f"{BASE_URL}/api/products/{product_id}", json={
        "name": "TEST Update Product", "category": "Pantry", "price": 15,
        "stock": 2, "available": False,
    })
    assert update.status_code == 200
    fetched = next(item for item in client.get(f"{BASE_URL}/api/products").json() if item["id"] == product_id)
    assert fetched["price"] == 15 and fetched["stock"] == 2 and fetched["available"] is False


def test_customer_update_persists_all_details(client):
    customer = client.post(f"{BASE_URL}/api/customers", json={
        "name": "TEST Update Customer", "phone": "9000000001", "address": "Old address",
        "society": "Prestige Ozone",
    })
    assert customer.status_code == 200
    customer_id = customer.json()["id"]
    update = client.put(f"{BASE_URL}/api/customers/{customer_id}", json={
        "name": "TEST Updated Customer", "phone": "9000000002", "address": "New address",
        "society": "Godrej Woods",
    })
    assert update.status_code == 200
    fetched = next(item for item in client.get(f"{BASE_URL}/api/customers").json() if item["id"] == customer_id)
    assert fetched["name"] == "TEST Updated Customer"
    assert fetched["phone"] == "9000000002" and fetched["society"] == "Godrej Woods"


def test_customer_update_rejects_unknown_society(client):
    customer = client.post(f"{BASE_URL}/api/customers", json={
        "name": "TEST Invalid Society Customer", "phone": "9000000003", "address": "Address",
        "society": "Prestige Ozone",
    })
    assert customer.status_code == 200
    customer_id = customer.json()["id"]
    response = client.put(f"{BASE_URL}/api/customers/{customer_id}", json={
        "name": "TEST Invalid Society Customer", "phone": "9000000003", "address": "Address",
        "society": "Not A Society",
    })
    assert response.status_code in (400, 422)


def test_order_status_rejects_unknown_status(client):
    orders = client.get(f"{BASE_URL}/api/orders")
    assert orders.status_code == 200
    if not orders.json():
        pytest.skip("No order exists for status validation")
    order_id = orders.json()[0]["id"]
    response = client.patch(f"{BASE_URL}/api/orders/{order_id}/status", params={"status": "Cancelled"})
    assert response.status_code in (400, 422)