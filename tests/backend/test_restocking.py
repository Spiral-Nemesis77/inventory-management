"""
Tests for restocking order endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_restocking_orders():
    """Reset the in-memory order list so tests don't leak state into each other."""
    main.restocking_orders.clear()
    yield
    main.restocking_orders.clear()


class TestDemandPricing:
    def test_demand_includes_cost_and_lead_time(self, client):
        response = client.get("/api/demand")
        assert response.status_code == 200
        for forecast in response.json():
            assert forecast["unit_cost"] > 0
            assert forecast["lead_time_days"] > 0


class TestCreateRestockingOrder:
    def test_create_order_success(self, client):
        payload = {
            "budget": 50000,
            "items": [
                {"item_sku": "WDG-001", "quantity": 100},  # 42.50, 10 days
                {"item_sku": "GSK-203", "quantity": 200},  # 12.75, 7 days
            ],
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201
        order = response.json()
        assert order["status"] == "Submitted"
        assert order["order_number"] == "RST-" + order["created_date"][:4] + "-0001"
        assert order["total_cost"] == pytest.approx(4250 + 2550)
        # Order lead time is the slowest line's lead time
        assert order["lead_time_days"] == 10
        assert len(order["items"]) == 2
        assert order["items"][0]["item_name"] == "Industrial Widget Type A"

    def test_server_pricing_ignores_client_price(self, client):
        payload = {
            "budget": 10000,
            "items": [{"item_sku": "WDG-001", "quantity": 10, "unit_cost": 0.01}],
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201
        assert response.json()["items"][0]["unit_cost"] == 42.5

    def test_unknown_sku_rejected(self, client):
        payload = {"budget": 10000, "items": [{"item_sku": "NOPE-999", "quantity": 1}]}
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 400

    def test_over_budget_rejected(self, client):
        payload = {"budget": 100, "items": [{"item_sku": "MTR-304", "quantity": 1}]}
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 400
        assert main.restocking_orders == []

    def test_empty_items_rejected(self, client):
        response = client.post("/api/restocking-orders", json={"budget": 1000, "items": []})
        assert response.status_code == 400

    def test_non_positive_quantity_rejected(self, client):
        payload = {"budget": 1000, "items": [{"item_sku": "WDG-001", "quantity": 0}]}
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 400


class TestListRestockingOrders:
    def test_empty_list(self, client):
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_newest_first(self, client):
        for sku in ["WDG-001", "FLT-405"]:
            client.post(
                "/api/restocking-orders",
                json={"budget": 10000, "items": [{"item_sku": sku, "quantity": 1}]},
            )
        orders = client.get("/api/restocking-orders").json()
        assert [o["items"][0]["item_sku"] for o in orders] == ["FLT-405", "WDG-001"]
