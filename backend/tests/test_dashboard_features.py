"""
Test Dashboard Features - Iteration 21
Tests for:
1. /api/stats endpoint returns date_range with from_date and to_date fields
2. /api/stats endpoint returns total_items field
3. Static PDF manual files are accessible with correct content-type
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestDashboardStatsEndpoint:
    """Tests for /api/stats endpoint - date_range and total_items"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_stats_endpoint_returns_date_range(self):
        """Verify /api/stats returns date_range object with from_date and to_date"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=self.headers)
        assert response.status_code == 200, f"Stats endpoint failed: {response.text}"
        
        data = response.json()
        
        # Verify date_range exists and has required fields
        assert "date_range" in data, "date_range field missing from /api/stats response"
        date_range = data["date_range"]
        assert "from_date" in date_range, "from_date missing from date_range"
        assert "to_date" in date_range, "to_date missing from date_range"
        
        # Verify dates are in YYYY-MM-DD format (backend format)
        from_date = date_range["from_date"]
        to_date = date_range["to_date"]
        if from_date:
            assert len(from_date.split('-')) == 3, f"from_date not in YYYY-MM-DD format: {from_date}"
        if to_date:
            assert len(to_date.split('-')) == 3, f"to_date not in YYYY-MM-DD format: {to_date}"
        
        print(f"✓ date_range returned: from_date={from_date}, to_date={to_date}")
    
    def test_stats_endpoint_returns_total_items(self):
        """Verify /api/stats returns total_items field"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "total_items" in data, "total_items field missing from /api/stats response"
        assert isinstance(data["total_items"], int), f"total_items should be int, got {type(data['total_items'])}"
        
        print(f"✓ total_items returned: {data['total_items']}")
    
    def test_stats_endpoint_contains_all_expected_fields(self):
        """Verify /api/stats returns all expected dashboard fields"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        
        # Check all expected fields
        expected_fields = [
            "total_transactions",
            "total_purchases", 
            "total_sales",
            "total_opening_stock",
            "total_parties",
            "total_items",
            "date_range"
        ]
        
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"
        
        # Verify stat values match expected (from test request)
        assert data["total_transactions"] == 11767, f"total_transactions mismatch: {data['total_transactions']}"
        assert data["total_parties"] == 1408, f"total_parties mismatch: {data['total_parties']}"
        assert data["total_purchases"] == 418, f"total_purchases mismatch: {data['total_purchases']}"
        assert data["total_sales"] == 10930, f"total_sales mismatch: {data['total_sales']}"
        
        print(f"✓ All expected fields present with correct values")
    
    def test_stats_date_range_matches_expected_values(self):
        """Verify date_range values match expected: 2026-01-15 to 2026-03-02"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        date_range = data.get("date_range", {})
        
        assert date_range.get("from_date") == "2026-01-15", \
            f"Expected from_date '2026-01-15', got '{date_range.get('from_date')}'"
        assert date_range.get("to_date") == "2026-03-02", \
            f"Expected to_date '2026-03-02', got '{date_range.get('to_date')}'"
        
        print(f"✓ Date range matches: {date_range['from_date']} to {date_range['to_date']}")


class TestPDFManualEndpoints:
    """Tests for static PDF manual files accessibility"""
    
    def test_english_manual_accessible(self):
        """Verify English manual PDF is accessible at /manuals/StockBud_Manual_EN.pdf"""
        response = requests.head(f"{BASE_URL}/manuals/StockBud_Manual_EN.pdf")
        
        assert response.status_code == 200, f"EN manual not accessible: {response.status_code}"
        assert "application/pdf" in response.headers.get("content-type", ""), \
            f"Wrong content-type: {response.headers.get('content-type')}"
        
        # Verify file has content (size > 0)
        content_length = int(response.headers.get("content-length", 0))
        assert content_length > 0, "EN manual is empty"
        
        print(f"✓ EN manual accessible: {content_length} bytes, content-type: application/pdf")
    
    def test_hindi_manual_accessible(self):
        """Verify Hindi manual PDF is accessible at /manuals/StockBud_Manual_HI.pdf"""
        response = requests.head(f"{BASE_URL}/manuals/StockBud_Manual_HI.pdf")
        
        assert response.status_code == 200, f"HI manual not accessible: {response.status_code}"
        assert "application/pdf" in response.headers.get("content-type", ""), \
            f"Wrong content-type: {response.headers.get('content-type')}"
        
        # Verify file has content (size > 0)
        content_length = int(response.headers.get("content-length", 0))
        assert content_length > 0, "HI manual is empty"
        
        print(f"✓ HI manual accessible: {content_length} bytes, content-type: application/pdf")
    
    def test_pdf_files_have_reasonable_size(self):
        """Verify PDFs are reasonably sized (between 100KB and 50MB)"""
        for lang, expected_min in [("EN", 100000), ("HI", 100000)]:
            response = requests.head(f"{BASE_URL}/manuals/StockBud_Manual_{lang}.pdf")
            assert response.status_code == 200
            
            content_length = int(response.headers.get("content-length", 0))
            assert content_length >= expected_min, \
                f"{lang} manual too small ({content_length} bytes), might be corrupted"
            assert content_length <= 50000000, \
                f"{lang} manual too large ({content_length} bytes)"
            
            print(f"✓ {lang} manual size OK: {content_length / 1024:.1f} KB")


class TestStatsEndpointSecurity:
    """Security tests for /api/stats endpoint"""
    
    def test_stats_requires_authentication(self):
        """Verify /api/stats requires authentication"""
        response = requests.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 403, f"Expected 403 without auth, got {response.status_code}"
        print("✓ /api/stats requires authentication")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
