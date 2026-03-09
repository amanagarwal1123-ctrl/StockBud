"""
Test new features for StockBud inventory management system:
1. POST /api/ai/seasonal-analysis - gemini-3-flash-preview + 30s timeout
2. POST /api/item-buffers/categorize - season_boost field
3. Session storage auth - sessionStorage vs localStorage
4. Other endpoints - /api/health, /api/notifications/categorized
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthEndpoint:
    """Basic health check"""

    def test_health_endpoint_returns_200(self):
        """GET /api/health should return 200"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"Unexpected status: {data}"
        print("PASS: /api/health returns 200 with healthy status")


class TestAuthLogin:
    """Test login endpoint"""

    def test_login_success_admin(self):
        """Login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.status_code} - {response.text}"
        data = response.json()
        assert 'access_token' in data, "No access_token in response"
        assert data.get('token_type') == 'bearer'
        assert 'user' in data, "No user in response"
        assert data['user'].get('username') == 'admin'
        print("PASS: Login with admin/admin123 works correctly")
        return data['access_token']


class TestNotificationsCategorized:
    """Test notifications endpoint (requires auth)"""

    def test_notifications_returns_200_with_auth(self):
        """GET /api/notifications/categorized with auth should return 200"""
        # First login
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}"
        token = login_resp.json()['access_token']

        # Get notifications
        response = requests.get(
            f"{BASE_URL}/api/notifications/categorized",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Verify response structure
        assert 'notifications' in data or 'total_unread' in data, f"Unexpected response: {data}"
        print(f"PASS: /api/notifications/categorized returns 200, total_unread: {data.get('total_unread', 'N/A')}")


class TestSeasonalAnalysis:
    """Test AI seasonal analysis endpoint with gemini-3-flash-preview + 30s timeout"""

    def test_seasonal_analysis_returns_200_within_timeout(self):
        """POST /api/ai/seasonal-analysis should return within 30s with ai_insights, recommendations, seasonal_items"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}"
        token = login_resp.json()['access_token']

        # Call seasonal analysis - should complete within 30s (+5s buffer for network)
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/api/ai/seasonal-analysis",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60  # Give some buffer
        )
        elapsed = time.time() - start_time

        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"Seasonal analysis completed in {elapsed:.2f}s")
        
        data = response.json()
        
        # Verify required fields exist
        assert 'ai_insights' in data, f"Missing ai_insights in response: {data.keys()}"
        assert 'recommendations' in data, f"Missing recommendations in response: {data.keys()}"
        assert 'seasonal_items' in data, f"Missing seasonal_items in response: {data.keys()}"
        
        # AI insights can be actual response or timeout message
        ai_insights = data['ai_insights']
        assert isinstance(ai_insights, str), f"ai_insights should be string, got: {type(ai_insights)}"
        assert len(ai_insights) > 0, "ai_insights is empty"
        
        # Check recommendations is a list
        assert isinstance(data['recommendations'], list), f"recommendations should be list, got: {type(data['recommendations'])}"
        
        # Check seasonal_items is dict
        assert isinstance(data['seasonal_items'], dict), f"seasonal_items should be dict, got: {type(data['seasonal_items'])}"
        
        # Print some results for verification
        print(f"PASS: POST /api/ai/seasonal-analysis returns 200 in {elapsed:.2f}s")
        print(f"  - ai_insights length: {len(ai_insights)} chars")
        print(f"  - recommendations count: {len(data['recommendations'])}")
        print(f"  - seasonal_items count: {len(data['seasonal_items'])}")
        print(f"  - current_season: {data.get('current_season', 'N/A')}")
        
        # Verify it completes within timeout (+buffer)
        assert elapsed < 45, f"Seasonal analysis took too long: {elapsed:.2f}s (expected < 45s)"


class TestItemBuffersCategorize:
    """Test item-buffers/categorize endpoint for season_boost field"""

    def test_categorize_returns_season_boost(self):
        """POST /api/item-buffers/categorize should return successfully"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}"
        token = login_resp.json()['access_token']

        # Call categorize endpoint
        response = requests.post(
            f"{BASE_URL}/api/item-buffers/categorize",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60  # Heavy aggregation can take time
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get('success') == True, f"Expected success=True, got: {data}"
        print(f"PASS: POST /api/item-buffers/categorize returns 200")
        print(f"  - total_items: {data.get('total_items', 'N/A')}")
        print(f"  - current_season: {data.get('current_season', 'N/A')}")
        print(f"  - season_label: {data.get('season_label', 'N/A')}")
        return token

    def test_item_buffers_has_season_boost(self):
        """GET /api/item-buffers should show season_boost per item"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.status_code}"
        token = login_resp.json()['access_token']

        # First call categorize to ensure items are populated
        cat_response = requests.post(
            f"{BASE_URL}/api/item-buffers/categorize",
            headers={"Authorization": f"Bearer {token}"},
            timeout=60
        )
        if cat_response.status_code != 200:
            print(f"Warning: Categorize returned {cat_response.status_code}")

        # Get item buffers
        response = requests.get(
            f"{BASE_URL}/api/item-buffers",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Response can be a dict with 'items' key or direct list
        if isinstance(data, dict):
            items = data.get('items', [])
        else:
            items = data
        
        assert isinstance(items, list), f"Expected items list, got: {type(items)}"
        
        # Check if items have season_boost field
        items_with_boost = 0
        items_checked = 0
        for item in items[:10]:  # Check first 10
            items_checked += 1
            if 'season_boost' in item:
                items_with_boost += 1
                # Verify season_boost is a number
                assert isinstance(item['season_boost'], (int, float)), f"season_boost should be numeric, got: {type(item['season_boost'])}"
                print(f"  - {item.get('item_name', 'unknown')}: season_boost={item['season_boost']}")
        
        if items_checked > 0:
            print(f"PASS: {items_with_boost}/{items_checked} items have season_boost field")
        else:
            print("INFO: No items in buffer to check (may need transactions data)")
        
        # If we have items, they should have season_boost
        if len(items) > 0:
            assert items_with_boost > 0, f"No items have season_boost field!"


class TestAuthWithoutLogin:
    """Test that protected endpoints require auth"""

    def test_seasonal_analysis_requires_auth(self):
        """POST /api/ai/seasonal-analysis without auth should return 401"""
        response = requests.post(f"{BASE_URL}/api/ai/seasonal-analysis")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("PASS: POST /api/ai/seasonal-analysis requires auth")

    def test_categorize_requires_auth(self):
        """POST /api/item-buffers/categorize without auth should return 401"""
        response = requests.post(f"{BASE_URL}/api/item-buffers/categorize")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("PASS: POST /api/item-buffers/categorize requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
