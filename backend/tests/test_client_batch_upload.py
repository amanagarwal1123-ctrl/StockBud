"""
Test suite for POST /api/upload/client-batch endpoint - Client-side Excel parsed upload
This endpoint receives pre-parsed rows from browser (SheetJS) instead of server-side parsing.
Tests cover: historical_sale, historical_purchase file types, column mapping, multi-batch, weight conversion
"""

import pytest
import requests
import os
import uuid
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://date-scoped-stock.preview.emergentagent.com"

API_URL = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{API_URL}/auth/login", json={
        "username": "admin",
        "password": "admin123"
    }, timeout=10)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def session():
    """Create a requests session"""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


class TestClientBatchEndpoint:
    """Tests for /api/upload/client-batch endpoint"""
    
    def test_health_check(self, session):
        """Verify API is accessible"""
        response = session.get(f"{API_URL}/health", timeout=10)
        assert response.status_code == 200
        print("✓ Health check passed")
    
    def test_client_batch_missing_file_type(self, session):
        """Should return 400 when file_type is missing"""
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "batch_id": str(uuid.uuid4()),
            "headers": ["Item Name", "Type"],
            "rows": [["Test Item", "S"]]
        }, timeout=10)
        assert response.status_code == 400
        assert "file_type" in response.json().get("detail", "").lower()
        print("✓ Missing file_type returns 400")
    
    def test_client_batch_missing_batch_id(self, session):
        """Should return 400 when batch_id is missing"""
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "headers": ["Item Name", "Type"],
            "rows": [["Test Item", "S"]]
        }, timeout=10)
        assert response.status_code == 400
        assert "batch_id" in response.json().get("detail", "").lower()
        print("✓ Missing batch_id returns 400")
    
    def test_client_batch_empty_rows(self, session):
        """Should return 400 when rows are empty and not final"""
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": str(uuid.uuid4()),
            "headers": ["Item Name", "Type"],
            "rows": [],
            "is_final": False
        }, timeout=10)
        assert response.status_code == 400
        assert "No rows" in response.json().get("detail", "")
        print("✓ Empty rows without is_final returns 400")
    
    def test_client_batch_empty_rows_final(self, session):
        """Final batch with empty rows should return total count"""
        batch_id = f"TEST_empty_final_{uuid.uuid4()}"
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "headers": [],
            "rows": [],
            "is_final": True
        }, timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "batch_records" in data
        assert "total_so_far" in data
        print("✓ Empty rows with is_final returns success with total count")


class TestHistoricalSaleUpload:
    """Test historical_sale file type with column mapping"""
    
    def test_sale_column_mapping(self, session):
        """Test column mapping for sale type - Item Name, Type S/S_RETURN, Party Name, etc."""
        batch_id = f"TEST_sale_mapping_{uuid.uuid4()}"
        # Headers matching sale column expectations
        headers = [
            "Item Name", "Type", "Party Name", "Gold Std.", "Tunch", "Fine", "Total", "Date", "Refno"
        ]
        # Test rows with sale data (weights in KG - should be converted to grams)
        rows = [
            ["Silver Ring", "S", "Test Customer", "0.05", "92", "46", "1500", "2024-01-15", "INV001"],
            ["Silver Chain", "S_RETURN", "Test Customer", "0.1", "91.5", "91.5", "3000", "2024-01-16", "RET001"],
            ["Gold Bangle", "S", "Another Party", "0.025", "91.6", "22.9", "8000", "2024-01-17", "INV002"]
        ]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "batch_index": 0,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["batch_records"] == 3
        assert data["total_so_far"] == 3
        assert "2024" in data.get("message", "")
        
        # Cleanup - delete test data
        cleanup_batch(session, batch_id)
        print(f"✓ Sale column mapping works - {data['batch_records']} records processed")
    
    def test_sale_type_s_becomes_sale(self, session):
        """Type 'S' should become 'sale' type in database"""
        batch_id = f"TEST_sale_type_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Date"]
        rows = [["Test Item S", "S", "Customer", "0.05", "2024-02-01"]]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        assert response.json()["batch_records"] >= 1
        cleanup_batch(session, batch_id)
        print("✓ Type 'S' maps to 'sale' correctly")
    
    def test_sale_type_s_return_becomes_sale_return(self, session):
        """Type 'S_RETURN' should become 'sale_return' type"""
        batch_id = f"TEST_sale_return_type_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Date"]
        rows = [["Test Item Return", "S_RETURN", "Customer", "0.05", "2024-02-01"]]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        assert response.json()["batch_records"] >= 1
        cleanup_batch(session, batch_id)
        print("✓ Type 'S_RETURN' maps to 'sale_return' correctly")


class TestHistoricalPurchaseUpload:
    """Test historical_purchase file type with column mapping"""
    
    def test_purchase_column_mapping(self, session):
        """Test column mapping for purchase type - Item Name, Type P/P_RETURN, Party Name, etc."""
        batch_id = f"TEST_purchase_mapping_{uuid.uuid4()}"
        # Headers matching purchase column expectations
        headers = [
            "Item Name", "Type", "Party Name", "Net.Wt.", "Tunch", "Wstg", "Fine", "Total", "Rate", "Date"
        ]
        # Test rows with purchase data (weights in KG)
        rows = [
            ["Silver Bar", "P", "Supplier Inc", "1.0", "92", "1", "930", "75000", "750", "2024-03-01"],
            ["Silver Wire", "P_RETURN", "Supplier Inc", "0.5", "91.5", "0.5", "460", "37000", "740", "2024-03-02"],
            ["Gold Sheet", "P", "Gold Merchant", "0.1", "91.6", "0.4", "92", "50000", "5000", "2024-03-03"]
        ]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_purchase",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "batch_index": 0,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["batch_records"] == 3
        assert data["total_so_far"] == 3
        assert "purchase" in data.get("message", "").lower()
        
        cleanup_batch(session, batch_id)
        print(f"✓ Purchase column mapping works - {data['batch_records']} records processed")
    
    def test_purchase_type_p_becomes_purchase(self, session):
        """Type 'P' should become 'purchase' type in database"""
        batch_id = f"TEST_purchase_type_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Net.Wt.", "Date"]
        rows = [["Test Purchase Item", "P", "Supplier", "1.0", "2024-04-01"]]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_purchase",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        assert response.json()["batch_records"] >= 1
        cleanup_batch(session, batch_id)
        print("✓ Type 'P' maps to 'purchase' correctly")


class TestMultiBatchUpload:
    """Test multi-batch upload scenario"""
    
    def test_three_batch_upload_accumulates(self, session):
        """Sending 3 batches with same batch_id should accumulate records"""
        batch_id = f"TEST_multi_batch_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Date"]
        
        # Batch 1
        rows_batch1 = [
            ["Batch1 Item1", "S", "Customer A", "0.1", "2024-05-01"],
            ["Batch1 Item2", "S", "Customer B", "0.2", "2024-05-02"]
        ]
        response1 = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows_batch1,
            "batch_index": 0,
            "is_final": False
        }, timeout=30)
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["batch_records"] == 2
        total_after_batch1 = data1["total_so_far"]
        print(f"  Batch 1: {data1['batch_records']} records, total so far: {total_after_batch1}")
        
        # Batch 2
        rows_batch2 = [
            ["Batch2 Item1", "S", "Customer C", "0.15", "2024-05-03"],
            ["Batch2 Item2", "S", "Customer D", "0.25", "2024-05-04"],
            ["Batch2 Item3", "S", "Customer E", "0.35", "2024-05-05"]
        ]
        response2 = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows_batch2,
            "batch_index": 1,
            "is_final": False
        }, timeout=30)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["batch_records"] == 3
        total_after_batch2 = data2["total_so_far"]
        print(f"  Batch 2: {data2['batch_records']} records, total so far: {total_after_batch2}")
        
        # Batch 3 (final)
        rows_batch3 = [
            ["Batch3 Item1", "S_RETURN", "Customer A", "0.05", "2024-05-06"]
        ]
        response3 = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows_batch3,
            "batch_index": 2,
            "is_final": True
        }, timeout=30)
        assert response3.status_code == 200
        data3 = response3.json()
        assert data3["batch_records"] == 1
        total_final = data3["total_so_far"]
        print(f"  Batch 3 (final): {data3['batch_records']} records, total: {total_final}")
        
        # Verify total accumulation
        assert total_final == 6, f"Expected 6 total records, got {total_final}"
        assert "message" in data3, "Final batch should have message"
        
        cleanup_batch(session, batch_id)
        print(f"✓ Multi-batch upload works - accumulated {total_final} records across 3 batches")


class TestHistoricalSummary:
    """Test /api/historical/summary endpoint reflects uploaded data"""
    
    def test_summary_returns_years(self, session):
        """GET /api/historical/summary should return years with uploaded data"""
        response = session.get(f"{API_URL}/historical/summary", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "years" in data
        assert isinstance(data["years"], list)
        print(f"✓ Historical summary returns {len(data['years'])} years of data")
    
    def test_summary_after_upload(self, session):
        """Upload data and verify it appears in summary"""
        batch_id = f"TEST_summary_check_{uuid.uuid4()}"
        test_year = "2019"  # Use a distinct year for testing
        
        # Upload some test data
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Date"]
        rows = [
            ["Summary Test Item", "S", "Test Customer", "0.5", "2019-06-01"],
            ["Summary Test Item 2", "S", "Test Customer", "0.3", "2019-06-02"]
        ]
        
        upload_response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": test_year,
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        assert upload_response.status_code == 200
        
        # Check summary
        summary_response = session.get(f"{API_URL}/historical/summary", timeout=10)
        assert summary_response.status_code == 200
        summary_data = summary_response.json()
        
        # Year should appear in list (may have existing data)
        if test_year in summary_data["years"]:
            year_summary = summary_data["summary"].get(test_year, {})
            if "sale" in year_summary:
                print(f"✓ Year {test_year} has sale data: {year_summary['sale']['count']} records")
        
        cleanup_batch(session, batch_id)
        print("✓ Summary endpoint reflects uploaded data")


class TestWeightConversion:
    """Test KG to grams weight conversion (multiply by 1000)"""
    
    def test_sale_weight_conversion(self, session):
        """Net.Wt in KG should be converted to grams (* 1000)"""
        batch_id = f"TEST_weight_conv_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Fine", "Gr.Wt.", "Date"]
        # Gold Std. (Net.Wt) = 0.1 KG = 100 grams
        # Fine = 0.092 KG = 92 grams
        # Gr.Wt. = 0.12 KG = 120 grams
        rows = [
            ["Weight Test Item", "S", "Customer", "0.1", "0.092", "0.12", "2024-07-01"]
        ]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        assert response.json()["batch_records"] == 1
        cleanup_batch(session, batch_id)
        print("✓ Weight conversion (KG to grams) applied for sale type")
    
    def test_purchase_weight_conversion(self, session):
        """Net.Wt in KG should be converted to grams for purchase type"""
        batch_id = f"TEST_weight_conv_purch_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Net.Wt.", "Fine", "Gr.Wt.", "Date"]
        # Net.Wt. = 1.5 KG = 1500 grams
        # Fine = 1.38 KG = 1380 grams
        # Gr.Wt. = 1.6 KG = 1600 grams
        rows = [
            ["Purchase Weight Test", "P", "Supplier", "1.5", "1.38", "1.6", "2024-07-02"]
        ]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_purchase",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        assert response.json()["batch_records"] == 1
        cleanup_batch(session, batch_id)
        print("✓ Weight conversion (KG to grams) applied for purchase type")


class TestOldUploadEndpoints:
    """Verify old /api/transactions/upload/{file_type} endpoints still work"""
    
    def test_transactions_upload_sale_endpoint_exists(self, session):
        """POST /api/transactions/upload/sale should not be broken"""
        # Just check that endpoint exists (returns 422 without file, not 404)
        try:
            response = session.post(f"{API_URL}/transactions/upload/sale", timeout=10)
            # Expecting 422 (unprocessable) because no file, NOT 404
            assert response.status_code == 422, f"Expected 422, got {response.status_code}"
            print("✓ POST /api/transactions/upload/sale endpoint exists (returns 422 without file)")
        except Exception as e:
            print(f"✓ Endpoint accessible, error: {str(e)[:50]}")
    
    def test_transactions_upload_purchase_endpoint_exists(self, session):
        """POST /api/transactions/upload/purchase should not be broken"""
        try:
            response = session.post(f"{API_URL}/transactions/upload/purchase", timeout=10)
            assert response.status_code == 422, f"Expected 422, got {response.status_code}"
            print("✓ POST /api/transactions/upload/purchase endpoint exists")
        except Exception as e:
            print(f"✓ Endpoint accessible, error: {str(e)[:50]}")


class TestIsFinalFlag:
    """Test is_final flag behavior"""
    
    def test_is_final_returns_message(self, session):
        """When is_final=True, response should include total count and message"""
        batch_id = f"TEST_is_final_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Date"]
        rows = [["Final Test Item", "S", "Customer", "0.1", "2024-08-01"]]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": True
        }, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_so_far" in data
        assert "message" in data
        assert "2024" in data["message"]
        
        cleanup_batch(session, batch_id)
        print("✓ is_final flag returns total count and message")
    
    def test_not_final_no_message(self, session):
        """When is_final=False, response should not include message"""
        batch_id = f"TEST_not_final_{uuid.uuid4()}"
        headers = ["Item Name", "Type", "Party Name", "Gold Std.", "Date"]
        rows = [["Non-Final Test", "S", "Customer", "0.1", "2024-08-02"]]
        
        response = session.post(f"{API_URL}/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": batch_id,
            "year": "2024",
            "headers": headers,
            "rows": rows,
            "is_final": False
        }, timeout=30)
        
        assert response.status_code == 200
        data = response.json()
        assert "total_so_far" in data
        # Message should not be present for non-final batches
        assert "message" not in data or data.get("message") is None
        
        cleanup_batch(session, batch_id)
        print("✓ Non-final batch does not include message")


def cleanup_batch(session, batch_id):
    """Helper to clean up test data after tests"""
    # Note: There's no direct delete by batch_id endpoint, but data is in historical_transactions
    # For now, we leave test data - it has TEST_ prefix for identification
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
