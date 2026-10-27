"""
Tests for report API endpoints.
"""
import pytest


class TestReportEndpoints:
    """Test suite for quarterly and monthly report endpoints."""

    def test_get_quarterly_report(self, client):
        """Test getting the quarterly report."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        for q in data:
            assert q["quarter"] in ["Q1-2025", "Q2-2025", "Q3-2025", "Q4-2025"]
            assert isinstance(q["total_orders"], int)
            assert 0 <= q["fulfillment_rate"] <= 100
            # Revenue is rounded server-side so no float drift reaches the UI
            assert q["total_revenue"] == round(q["total_revenue"], 2)

        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_get_monthly_trends(self, client):
        """Test getting monthly trends."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for m in data:
            assert len(m["month"]) == 7
            assert m["revenue"] == round(m["revenue"], 2)

        months = [m["month"] for m in data]
        assert months == sorted(months)

    @pytest.mark.parametrize("query", [
        "warehouse=Tokyo",
        "category=sensors",
        "status=Delivered",
        "month=2025-03",
        "month=Q2-2025",
        "warehouse=London&category=sensors&status=Shipped",
    ])
    def test_reports_match_filtered_orders(self, client, query):
        """Test that reports aggregate exactly the orders the same filters return."""
        filtered_orders = client.get(f"/api/orders?{query}").json()
        quarterly = client.get(f"/api/reports/quarterly?{query}").json()
        monthly = client.get(f"/api/reports/monthly-trends?{query}").json()

        expected_revenue = sum(o["total_value"] for o in filtered_orders)
        assert sum(m["order_count"] for m in monthly) == len(filtered_orders)
        assert sum(q["total_orders"] for q in quarterly) == len(filtered_orders)
        assert abs(sum(m["revenue"] for m in monthly) - expected_revenue) < 0.01
        assert abs(sum(q["total_revenue"] for q in quarterly) - expected_revenue) < 0.01

    def test_reports_single_month_filter(self, client):
        """Test that a month filter narrows reports to that month and its quarter."""
        monthly = client.get("/api/reports/monthly-trends?month=2025-03").json()
        quarterly = client.get("/api/reports/quarterly?month=2025-03").json()
        assert [m["month"] for m in monthly] == ["2025-03"]
        assert [q["quarter"] for q in quarterly] == ["Q1-2025"]

    def test_reports_no_matches(self, client):
        """Test that filters matching nothing return empty lists."""
        for path in ("/api/reports/quarterly", "/api/reports/monthly-trends"):
            response = client.get(f"{path}?warehouse=Nowhere")
            assert response.status_code == 200
            assert response.json() == []

    def test_reports_all_filter_value(self, client):
        """Test that 'all' filter values are treated as no filter."""
        unfiltered = client.get("/api/reports/monthly-trends").json()
        all_values = client.get(
            "/api/reports/monthly-trends?warehouse=all&category=all&status=all&month=all"
        ).json()
        assert all_values == unfiltered
