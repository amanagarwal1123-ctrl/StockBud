"""
Test suite for Historical Profit Analysis and Chunked Upload APIs
Features tested:
- GET /api/analytics/historical-profit (yearly, customer, supplier, item, month views)
- POST /api/upload/init (chunked upload initialization)
- POST /api/upload/chunk/{id} (chunk upload)
- POST /api/upload/finalize/{id} (finalize upload)
- GET /api/upload/status/{id} (upload status)
- GET /api/stats (dashboard stats - should NOT include historical data)
"""
import pytest
import requests
import os
import time
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://profit-planner-16.preview.emergentagent.com"


class TestHealthCheck:
    """Basic health check"""
    
    def test_health_endpoint(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("PASSED: Health check endpoint returns 200 OK")


class TestHistoricalProfitYearly:
    """Historical profit - Yearly view tests"""
    
    def test_yearly_summary_with_year(self):
        """GET /api/analytics/historical-profit?year=2025&view=yearly"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?year=2025&view=yearly")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "view" in data and data["view"] == "yearly"
        assert "year" in data
        assert "silver_profit_kg" in data
        assert "labor_profit_inr" in data
        assert "total_sold_kg" in data
        assert "total_transactions" in data
        assert "total_sale_records" in data
        assert "total_purchase_records" in data
        
        # Verify data types
        assert isinstance(data["silver_profit_kg"], (int, float))
        assert isinstance(data["labor_profit_inr"], (int, float))
        assert isinstance(data["total_sold_kg"], (int, float))
        assert isinstance(data["total_transactions"], int)
        
        print(f"PASSED: Yearly summary - Silver profit: {data['silver_profit_kg']} kg, "
              f"Labour profit: {data['labor_profit_inr']} INR, "
              f"Transactions matched: {data['total_transactions']}")
    
    def test_yearly_summary_without_year(self):
        """GET /api/analytics/historical-profit?view=yearly (no year param)"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?view=yearly")
        assert response.status_code == 200
        data = response.json()
        
        assert data["view"] == "yearly"
        assert "silver_profit_kg" in data
        assert "labor_profit_inr" in data
        print(f"PASSED: Yearly summary without year param works")


class TestHistoricalProfitCustomer:
    """Historical profit - Customer-wise view tests"""
    
    def test_customer_wise_profit(self):
        """GET /api/analytics/historical-profit?year=2025&view=customer"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?year=2025&view=customer")
        assert response.status_code == 200
        data = response.json()
        
        assert data["view"] == "customer"
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        assert data["total"] > 0, "Should have at least some customer data"
        
        # Check first record structure
        if len(data["data"]) > 0:
            first = data["data"][0]
            assert "name" in first
            assert "silver_profit_kg" in first
            assert "labor_profit_inr" in first
            assert "total_sold_kg" in first
            assert "transactions" in first
        
        # Verify sorted by silver_profit_kg descending
        if len(data["data"]) > 1:
            assert data["data"][0]["silver_profit_kg"] >= data["data"][1]["silver_profit_kg"], \
                "Should be sorted by silver_profit_kg descending"
        
        print(f"PASSED: Customer-wise profit - {data['total']} customers, "
              f"Top customer: {data['data'][0]['name'] if data['data'] else 'N/A'}")


class TestHistoricalProfitSupplier:
    """Historical profit - Supplier-wise view tests"""
    
    def test_supplier_wise_profit(self):
        """GET /api/analytics/historical-profit?year=2025&view=supplier"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?year=2025&view=supplier")
        assert response.status_code == 200
        data = response.json()
        
        assert data["view"] == "supplier"
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        
        # Check first record structure
        if len(data["data"]) > 0:
            first = data["data"][0]
            assert "name" in first
            assert "silver_profit_kg" in first
            assert "labor_profit_inr" in first
            assert "total_purchased_kg" in first  # Supplier uses total_purchased_kg
            assert "items_count" in first
        
        print(f"PASSED: Supplier-wise profit - {data['total']} suppliers")


class TestHistoricalProfitItem:
    """Historical profit - Item-wise view tests"""
    
    def test_item_wise_profit(self):
        """GET /api/analytics/historical-profit?year=2025&view=item"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?year=2025&view=item")
        assert response.status_code == 200
        data = response.json()
        
        assert data["view"] == "item"
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        
        # Check first record structure
        if len(data["data"]) > 0:
            first = data["data"][0]
            assert "name" in first
            assert "silver_profit_kg" in first
            assert "labor_profit_inr" in first
            assert "total_sold_kg" in first
            assert "avg_purchase_tunch" in first
            assert "avg_sale_tunch" in first
            assert "transactions" in first
        
        print(f"PASSED: Item-wise profit - {data['total']} items, "
              f"Top item: {data['data'][0]['name'] if data['data'] else 'N/A'}")


class TestHistoricalProfitMonth:
    """Historical profit - Month-wise view tests"""
    
    def test_month_wise_profit(self):
        """GET /api/analytics/historical-profit?year=2025&view=month"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?year=2025&view=month")
        assert response.status_code == 200
        data = response.json()
        
        assert data["view"] == "month"
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)
        
        # Check first record structure
        if len(data["data"]) > 0:
            first = data["data"][0]
            assert "month" in first  # Month uses 'month' instead of 'name'
            assert "silver_profit_kg" in first
            assert "labor_profit_inr" in first
            assert "total_sold_kg" in first
            assert "transactions" in first
        
        # Verify sorted chronologically (ascending by month)
        if len(data["data"]) > 1:
            assert data["data"][0]["month"] <= data["data"][1]["month"], \
                "Should be sorted chronologically"
        
        print(f"PASSED: Month-wise profit - {data['total']} months")


class TestHistoricalProfitInvalidView:
    """Historical profit - Invalid view handling"""
    
    def test_invalid_view_returns_400(self):
        """GET /api/analytics/historical-profit?view=invalid"""
        response = requests.get(f"{BASE_URL}/api/analytics/historical-profit?view=invalid")
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print("PASSED: Invalid view returns 400 with detail message")


class TestChunkedUploadInit:
    """Chunked upload initialization tests"""
    
    def test_init_upload_sale(self):
        """POST /api/upload/init for sale file"""
        response = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={
                "file_type": "sale",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31",
                "total_chunks": 2
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        assert len(data["upload_id"]) > 0
        print(f"PASSED: Upload init returns upload_id: {data['upload_id'][:8]}...")
    
    def test_init_upload_purchase(self):
        """POST /api/upload/init for purchase file"""
        response = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={
                "file_type": "purchase",
                "year": "2025"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        print(f"PASSED: Upload init for purchase returns upload_id")
    
    def test_init_upload_historical_sale(self):
        """POST /api/upload/init for historical_sale file"""
        response = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={
                "file_type": "historical_sale",
                "year": "2025"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        print(f"PASSED: Upload init for historical_sale returns upload_id")
    
    def test_init_upload_historical_purchase(self):
        """POST /api/upload/init for historical_purchase file"""
        response = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={
                "file_type": "historical_purchase",
                "year": "2025"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        print(f"PASSED: Upload init for historical_purchase returns upload_id")
    
    def test_init_upload_invalid_type(self):
        """POST /api/upload/init with invalid file_type"""
        response = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={"file_type": "invalid_type"}
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        print(f"PASSED: Invalid file_type returns 400")


class TestChunkedUploadStatus:
    """Upload status endpoint tests"""
    
    def test_status_nonexistent_upload(self):
        """GET /api/upload/status/{id} for non-existent ID returns 404"""
        response = requests.get(f"{BASE_URL}/api/upload/status/nonexistent-upload-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print("PASSED: Non-existent upload ID returns 404")
    
    def test_status_existing_upload(self):
        """GET /api/upload/status/{id} for existing upload"""
        # First create an upload session
        init_resp = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={"file_type": "sale", "total_chunks": 1}
        )
        assert init_resp.status_code == 200
        upload_id = init_resp.json()["upload_id"]
        
        # Check status (should be processing or similar)
        status_resp = requests.get(f"{BASE_URL}/api/upload/status/{upload_id}")
        # Status can be 200 (processing) or 404 if session cleaned up
        assert status_resp.status_code in [200, 404]
        
        if status_resp.status_code == 200:
            data = status_resp.json()
            assert "status" in data
            print(f"PASSED: Upload status returns status field: {data['status']}")
        else:
            print("PASSED: Upload status returns 404 (session may have been cleaned up)")


class TestDashboardStatsExcludesHistorical:
    """Verify dashboard stats don't include historical data"""
    
    def test_stats_excludes_historical(self):
        """GET /api/stats should NOT include historical_transactions data"""
        response = requests.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Check expected fields
        assert "total_transactions" in data
        assert "total_purchases" in data
        assert "total_sales" in data
        assert "total_opening_stock" in data
        assert "total_parties" in data
        
        # Historical data has ~211k records. Stats should be much lower (<5000)
        # This verifies stats only counts from 'transactions' collection, not 'historical_transactions'
        assert data["total_transactions"] < 10000, \
            f"total_transactions ({data['total_transactions']}) should be < 10000 (historical has 200k+)"
        
        print(f"PASSED: Dashboard stats excludes historical data - "
              f"total_transactions: {data['total_transactions']} (< 10000)")


class TestChunkedUploadFinalize:
    """Chunked upload finalize endpoint tests"""
    
    def test_finalize_nonexistent_upload(self):
        """POST /api/upload/finalize/{id} for non-existent ID returns 404"""
        response = requests.post(f"{BASE_URL}/api/upload/finalize/nonexistent-upload-id")
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print("PASSED: Finalize non-existent upload returns 404")
    
    def test_finalize_without_chunks(self):
        """POST /api/upload/finalize/{id} without chunks returns 400"""
        # Create upload session
        init_resp = requests.post(
            f"{BASE_URL}/api/upload/init",
            json={"file_type": "sale", "total_chunks": 1}
        )
        upload_id = init_resp.json()["upload_id"]
        
        # Try to finalize without uploading chunks
        finalize_resp = requests.post(f"{BASE_URL}/api/upload/finalize/{upload_id}")
        # Should fail because no chunks uploaded
        assert finalize_resp.status_code == 400
        data = finalize_resp.json()
        assert "detail" in data
        print("PASSED: Finalize without chunks returns 400")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
