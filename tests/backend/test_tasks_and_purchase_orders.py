"""
Tests for task and purchase order endpoints.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clear_in_memory_state():
    """Reset in-memory tasks and purchase orders so tests don't leak state into each other."""
    main.tasks.clear()
    main.purchase_orders.clear()
    yield
    main.tasks.clear()
    main.purchase_orders.clear()


def make_po_payload(backlog_item_id="1", **overrides):
    payload = {
        "backlog_item_id": backlog_item_id,
        "supplier_name": "Acme Supply",
        "quantity": 350,
        "unit_cost": 12.5,
        "expected_delivery_date": "2025-11-15",
        "notes": "Expedite",
    }
    payload.update(overrides)
    return payload


class TestTaskEndpoints:
    """Test suite for task endpoints."""

    def test_get_all_tasks_empty(self, client):
        """Test that the task list starts empty."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task."""
        response = client.post(
            "/api/tasks", json={"title": "  Check stock  ", "priority": "high", "dueDate": "2025-11-01"}
        )
        assert response.status_code == 201

        task = response.json()
        assert task["title"] == "Check stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2025-11-01"
        assert task["status"] == "pending"
        # Prefixed so IDs never collide with the client's numeric mock task IDs
        assert task["id"].startswith("task-")

        assert client.get("/api/tasks").json() == [task]

    def test_create_task_blank_title(self, client):
        """Test that a blank title is rejected."""
        response = client.post("/api/tasks", json={"title": "   ", "dueDate": "2025-11-01"})
        assert response.status_code == 400

    def test_create_task_missing_due_date(self, client):
        """Test that a missing due date fails validation."""
        response = client.post("/api/tasks", json={"title": "Check stock"})
        assert response.status_code == 422

    def test_task_ids_unique_after_delete(self, client):
        """Test that deleting a task doesn't cause a later task to reuse its ID."""
        first = client.post("/api/tasks", json={"title": "A", "dueDate": "2025-11-01"}).json()
        second = client.post("/api/tasks", json={"title": "B", "dueDate": "2025-11-01"}).json()
        client.delete(f"/api/tasks/{first['id']}")
        third = client.post("/api/tasks", json={"title": "C", "dueDate": "2025-11-01"}).json()
        assert third["id"] not in (first["id"], second["id"])

    def test_toggle_task(self, client):
        """Test toggling a task between pending and completed."""
        task = client.post("/api/tasks", json={"title": "A", "dueDate": "2025-11-01"}).json()

        response = client.patch(f"/api/tasks/{task['id']}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        response = client.patch(f"/api/tasks/{task['id']}")
        assert response.json()["status"] == "pending"

    def test_delete_task(self, client):
        """Test deleting a task."""
        task = client.post("/api/tasks", json={"title": "A", "dueDate": "2025-11-01"}).json()

        response = client.delete(f"/api/tasks/{task['id']}")
        assert response.status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_nonexistent_task(self, client):
        """Test toggling and deleting a task that doesn't exist."""
        for method in (client.patch, client.delete):
            response = method("/api/tasks/task-999")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()


class TestPurchaseOrderEndpoints:
    """Test suite for purchase order endpoints."""

    def test_create_purchase_order(self, client):
        """Test creating a purchase order for a backlog item."""
        response = client.post("/api/purchase-orders", json=make_po_payload())
        assert response.status_code == 201

        po = response.json()
        assert po["backlog_item_id"] == "1"
        assert po["supplier_name"] == "Acme Supply"
        assert po["quantity"] == 350
        assert po["status"] == "pending"
        assert po["notes"] == "Expedite"
        assert po["id"] == "PO-" + po["created_date"][:4] + "-0001"

    def test_backlog_reflects_purchase_order(self, client):
        """Test that the backlog reports the PO once it exists."""
        backlog = client.get("/api/backlog").json()
        item = next(b for b in backlog if b["id"] == "1")
        assert item["has_purchase_order"] is False
        assert item["purchase_order_id"] is None

        po = client.post("/api/purchase-orders", json=make_po_payload()).json()

        backlog = client.get("/api/backlog").json()
        item = next(b for b in backlog if b["id"] == "1")
        assert item["has_purchase_order"] is True
        assert item["purchase_order_id"] == po["id"]

    def test_get_purchase_order_by_backlog_item(self, client):
        """Test fetching the PO attached to a backlog item."""
        po = client.post("/api/purchase-orders", json=make_po_payload()).json()

        response = client.get("/api/purchase-orders/backlog/1")
        assert response.status_code == 200
        assert response.json() == po

    def test_get_nonexistent_purchase_order(self, client):
        """Test fetching a PO for a backlog item that has none."""
        response = client.get("/api/purchase-orders/backlog/1")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_purchase_order_unknown_backlog_item(self, client):
        """Test that a PO for an unknown backlog item is rejected."""
        response = client.post("/api/purchase-orders", json=make_po_payload(backlog_item_id="999"))
        assert response.status_code == 404

    def test_create_duplicate_purchase_order(self, client):
        """Test that a backlog item can only have one PO."""
        client.post("/api/purchase-orders", json=make_po_payload())
        response = client.post("/api/purchase-orders", json=make_po_payload())
        assert response.status_code == 409

    @pytest.mark.parametrize("overrides", [{"quantity": 0}, {"quantity": -5}, {"unit_cost": -1}])
    def test_create_purchase_order_invalid_values(self, client, overrides):
        """Test that non-positive quantities and negative costs are rejected."""
        response = client.post("/api/purchase-orders", json=make_po_payload(**overrides))
        assert response.status_code == 400
