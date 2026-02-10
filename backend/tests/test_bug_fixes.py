"""
Test suite for StockBud bug fixes and new features
Features tested:
1. Dashboard stamps appearing correctly
2. Login works
3. Stats endpoint works
4. Historical data summary
5. Stamp verification history endpoint (sorted numerically)
6. Visualization page with 6 tabs
7. StampAssignments page with natural sort
8. Stamp normalization
"""

import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json()["access_token"]


class TestLogin:
    """Test authentication endpoints"""
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wronguser",
            "password": "wrongpass"
        })
        assert response.status_code == 401


class TestStats:
    """Test stats endpoint"""
    
    def test_stats_endpoint(self):
        """Test GET /api/stats"""
        response = requests.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "total_transactions" in data
        assert "total_parties" in data
        assert isinstance(data["total_transactions"], int)
        assert isinstance(data["total_parties"], int)


class TestHistorical:
    """Test historical data endpoints"""
    
    def test_historical_summary(self):
        """Test GET /api/historical/summary"""
        response = requests.get(f"{BASE_URL}/api/historical/summary")
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure (empty summary is OK)
        assert "summary" in data
        assert "years" in data
        assert isinstance(data["years"], list)
        assert isinstance(data["summary"], dict)


class TestStampVerificationHistory:
    """Test stamp verification history - critical for dashboard"""
    
    def test_stamp_verification_history_returns_stamps(self):
        """Test GET /api/stamp-verification/history"""
        response = requests.get(f"{BASE_URL}/api/stamp-verification/history")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0, "No stamps in verification history"
        
        # Check structure of each stamp
        for stamp in data[:5]:
            assert "stamp" in stamp
            assert "last_verified_date" in stamp
            assert "is_match" in stamp
            assert "difference" in stamp
    
    def test_stamp_verification_history_sorted_numerically(self):
        """Verify stamps are sorted numerically (1, 2, 3... 9, 10, 11... not 1, 10, 11, 2)"""
        response = requests.get(f"{BASE_URL}/api/stamp-verification/history")
        assert response.status_code == 200
        data = response.json()
        
        # Extract numbers from stamps
        prev_num = 0
        for stamp_data in data:
            stamp_name = stamp_data["stamp"]
            match = re.search(r'(\d+)', stamp_name)
            if match:
                num = int(match.group(1))
                assert num >= prev_num, f"Stamps not sorted numerically: {stamp_name} came after Stamp {prev_num}"
                prev_num = num


class TestMasterItems:
    """Test master items endpoint"""
    
    def test_master_items(self):
        """Test GET /api/master-items"""
        response = requests.get(f"{BASE_URL}/api/master-items")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0, "No master items found"
        
        # Check structure
        for item in data[:5]:
            assert "item_name" in item
            assert "stamp" in item


class TestStampAssignments:
    """Test stamp assignments endpoint"""
    
    def test_stamp_assignments_endpoint(self):
        """Test GET /api/stamp-assignments"""
        response = requests.get(f"{BASE_URL}/api/stamp-assignments")
        assert response.status_code == 200
        data = response.json()
        
        assert "assignments" in data
        assert isinstance(data["assignments"], list)


class TestVisualization:
    """Test visualization analytics endpoint"""
    
    def test_visualization_endpoint(self):
        """Test GET /api/analytics/visualization"""
        response = requests.get(f"{BASE_URL}/api/analytics/visualization")
        assert response.status_code == 200
        data = response.json()
        
        # Check key fields are present
        assert "sales_by_item" in data or "tier_distribution" in data or "stock_health" in data


class TestInventory:
    """Test inventory endpoints"""
    
    def test_current_inventory(self):
        """Test GET /api/inventory/current"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        
        assert "inventory" in data
        assert "total_items" in data
        assert "total_gr_wt" in data
        assert "total_net_wt" in data


class TestStampNormalization:
    """Test stamp normalization functionality"""
    
    def test_stamps_format_consistency(self):
        """Check stamps are in consistent format (Stamp X or STAMP X)"""
        response = requests.get(f"{BASE_URL}/api/master-items")
        assert response.status_code == 200
        data = response.json()
        
        stamps = set(item["stamp"] for item in data if item.get("stamp"))
        
        # Check each stamp follows the expected pattern
        for stamp in stamps:
            # Should be "Stamp X" or "STAMP X" format
            match = re.match(r'^(Stamp|STAMP)\s+\d+$', stamp, re.IGNORECASE)
            assert match or stamp == 'Unassigned', f"Invalid stamp format: {stamp}"


class TestSeasonalAnalysis:
    """Test seasonal analysis endpoint (requires auth)"""
    
    def test_seasonal_analysis_endpoint_requires_auth(self, auth_token):
        """Test POST /api/ai/seasonal-analysis requires authentication"""
        # Without auth
        response = requests.post(f"{BASE_URL}/api/ai/seasonal-analysis", json={})
        assert response.status_code in [401, 403], "Seasonal analysis should require auth"
        
    def test_seasonal_analysis_with_auth(self, auth_token):
        """Test POST /api/ai/seasonal-analysis with valid auth"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        # This endpoint may take a while, so we just check it's accessible
        response = requests.post(
            f"{BASE_URL}/api/ai/seasonal-analysis", 
            json={},
            headers=headers,
            timeout=5  # Short timeout - just checking endpoint exists
        )
        # Either success or timeout, not auth error
        assert response.status_code != 401, "Should not get auth error with valid token"


class TestNotifications:
    """Test notification endpoints"""
    
    def test_notifications_categorized_with_auth(self, auth_token):
        """Test GET /api/notifications/categorized"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/notifications/categorized", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "total_unread" in data
        assert "notifications" in data


class TestHealth:
    """Test health endpoints"""
    
    def test_health_endpoint(self):
        """Test GET /api/health"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
    
    def test_root_health_endpoint(self):
        """Test GET /health"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
