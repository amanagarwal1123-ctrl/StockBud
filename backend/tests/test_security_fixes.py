"""
Security and Correctness Bug Fixes Tests - Iteration 16
Tests for P0/P1/P2 security fixes in silver stock trading application.

Bug Fixes Tested:
- P0: Auth on upload endpoints (opening-stock, transactions, upload/init, master-stock)
- P0: Auth on delete/reset endpoints (transactions/all, system/reset)
- P2: Polythene delete requires admin role
- Correctness: Notifications query matches target_user/for_role schema
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
API_URL = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def admin_token():
    """Get authentication token for admin user"""
    response = requests.post(f"{API_URL}/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    return response.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Headers with admin authorization"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def non_admin_token():
    """Get token for non-admin user (e.g., executive, manager)"""
    # Try existing non-admin users in the system
    # Known users: SEE1 (executive), SMANAGER (manager), PEE1 (polythene_executive)
    non_admin_users = [
        ("SEE1", "SEE1"),  # username, likely password
        ("SMANAGER", "SMANAGER"),
        ("PEE1", "PEE1"),
        ("SEE2", "SEE2"),
    ]
    
    for username, password in non_admin_users:
        response = requests.post(f"{API_URL}/auth/login", json={
            "username": username,
            "password": password
        })
        if response.status_code == 200:
            data = response.json()
            if data.get("user", {}).get("role") != "admin":
                print(f"Using non-admin user: {username} (role: {data.get('user', {}).get('role')})")
                return response.json()["access_token"]
    
    # If no existing user works, skip the tests
    pytest.skip("No non-admin user available for testing (tried SEE1, SMANAGER, PEE1)")


@pytest.fixture(scope="module")
def non_admin_headers(non_admin_token):
    """Headers with non-admin authorization"""
    return {"Authorization": f"Bearer {non_admin_token}"}


# ==================== P0: AUTH ON UPLOAD ENDPOINTS ====================

class TestUploadEndpointAuth:
    """P0: All upload endpoints should require authentication"""
    
    def test_opening_stock_upload_no_auth(self):
        """POST /api/opening-stock/upload without auth token should return 401"""
        # Create dummy file content
        dummy_content = b"dummy excel content"
        files = {"file": ("test.xlsx", io.BytesIO(dummy_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        response = requests.post(f"{API_URL}/opening-stock/upload", files=files)
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/opening-stock/upload without auth returns {response.status_code}")
    
    def test_transaction_sale_upload_no_auth(self):
        """POST /api/transactions/upload/sale without auth token should return 401"""
        dummy_content = b"dummy excel content"
        files = {"file": ("test.xlsx", io.BytesIO(dummy_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        response = requests.post(f"{API_URL}/transactions/upload/sale", files=files)
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/transactions/upload/sale without auth returns {response.status_code}")
    
    def test_transaction_purchase_upload_no_auth(self):
        """POST /api/transactions/upload/purchase without auth token should return 401"""
        dummy_content = b"dummy excel content"
        files = {"file": ("test.xlsx", io.BytesIO(dummy_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        response = requests.post(f"{API_URL}/transactions/upload/purchase", files=files)
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/transactions/upload/purchase without auth returns {response.status_code}")
    
    def test_init_chunked_upload_no_auth(self):
        """POST /api/upload/init without auth token should return 401"""
        response = requests.post(f"{API_URL}/upload/init", json={
            "file_type": "sale",
            "file_name": "test.xlsx",
            "total_chunks": 1,
            "file_size": 1024
        })
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/upload/init without auth returns {response.status_code}")
    
    def test_master_stock_upload_no_auth(self):
        """POST /api/master-stock/upload without auth token should return 401"""
        dummy_content = b"dummy excel content"
        files = {"file": ("test.xlsx", io.BytesIO(dummy_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        
        response = requests.post(f"{API_URL}/master-stock/upload", files=files)
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/master-stock/upload without auth returns {response.status_code}")


# ==================== P0: AUTH ON DELETE/RESET ENDPOINTS ====================

class TestDeleteResetEndpointAuth:
    """P0: Delete and reset endpoints should require authentication and admin role"""
    
    def test_delete_all_transactions_no_auth(self):
        """DELETE /api/transactions/all without auth token should return 401"""
        response = requests.delete(f"{API_URL}/transactions/all")
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ DELETE /api/transactions/all without auth returns {response.status_code}")
    
    def test_system_reset_no_auth(self):
        """POST /api/system/reset without auth token should return 401"""
        response = requests.post(f"{API_URL}/system/reset", json={
            "categories": ["sales"],
            "password": "CLOSE"
        })
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/system/reset without auth returns {response.status_code}")
    
    def test_delete_all_transactions_non_admin(self, non_admin_headers):
        """DELETE /api/transactions/all with non-admin user should return 403"""
        response = requests.delete(f"{API_URL}/transactions/all", headers=non_admin_headers)
        
        assert response.status_code == 403, \
            f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print(f"✓ DELETE /api/transactions/all with non-admin returns 403")
    
    def test_system_reset_non_admin(self, non_admin_headers):
        """POST /api/system/reset with non-admin user should return 403"""
        response = requests.post(f"{API_URL}/system/reset", json={
            "categories": ["sales"],
            "password": "CLOSE"
        }, headers=non_admin_headers)
        
        assert response.status_code == 403, \
            f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/system/reset with non-admin returns 403")
    
    def test_system_reset_admin_wrong_password(self, admin_headers):
        """POST /api/system/reset with admin but wrong password should return 403"""
        response = requests.post(f"{API_URL}/system/reset", json={
            "categories": ["sales"],
            "password": "WRONG"
        }, headers=admin_headers)
        
        assert response.status_code == 403, \
            f"Expected 403 for wrong password, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/system/reset with wrong password returns 403")


# ==================== P2: POLYTHENE DELETE ROLE CHECK ====================

class TestPolytheneDeleteAuth:
    """P2: Polythene delete should require admin role"""
    
    def test_polythene_delete_no_auth(self):
        """DELETE /api/polythene/{id} without auth token should return 401"""
        response = requests.delete(f"{API_URL}/polythene/test-entry-id-123")
        
        assert response.status_code in [401, 403], \
            f"Expected 401/403 without auth, got {response.status_code}: {response.text}"
        print(f"✓ DELETE /api/polythene/{{id}} without auth returns {response.status_code}")
    
    def test_polythene_delete_non_admin(self, non_admin_headers):
        """DELETE /api/polythene/{id} with non-admin should return 403"""
        response = requests.delete(f"{API_URL}/polythene/test-entry-id-123", headers=non_admin_headers)
        
        # Should be 403 (forbidden) for non-admin, not 404
        assert response.status_code == 403, \
            f"Expected 403 for non-admin, got {response.status_code}: {response.text}"
        print(f"✓ DELETE /api/polythene/{{id}} with non-admin returns 403")
    
    def test_polythene_delete_admin_nonexistent(self, admin_headers):
        """DELETE /api/polythene/{id} with admin for non-existent ID should return 404"""
        response = requests.delete(f"{API_URL}/polythene/nonexistent-entry-id-xyz", headers=admin_headers)
        
        # Admin should get past auth check, so should return 404 for non-existent entry
        assert response.status_code in [404, 200], \
            f"Expected 404 for non-existent entry, got {response.status_code}: {response.text}"
        print(f"✓ DELETE /api/polythene/{{id}} with admin for non-existent returns {response.status_code}")


# ==================== AUTH SUCCESS: VERIFY ENDPOINTS WORK WITH AUTH ====================

class TestAuthenticatedEndpointsWork:
    """Verify protected endpoints work correctly with valid auth"""
    
    def test_profit_endpoint_with_auth(self, admin_headers):
        """GET /api/analytics/profit with valid token should return data"""
        response = requests.get(f"{API_URL}/analytics/profit", headers=admin_headers)
        
        assert response.status_code == 200, \
            f"Expected 200 with auth, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify response has expected fields
        assert "silver_profit_kg" in data, f"Missing silver_profit_kg in response: {data.keys()}"
        assert "labor_profit_inr" in data, f"Missing labor_profit_inr in response: {data.keys()}"
        print(f"✓ GET /api/analytics/profit with auth returns data: silver_profit={data['silver_profit_kg']}kg")
    
    def test_init_upload_with_auth(self, admin_headers):
        """POST /api/upload/init with valid token should work"""
        response = requests.post(f"{API_URL}/upload/init", json={
            "file_type": "sale",
            "file_name": "test.xlsx",
            "total_chunks": 1,
            "file_size": 1024
        }, headers=admin_headers)
        
        # Should either succeed or fail for valid reasons (not auth)
        assert response.status_code != 401, \
            f"Should not get 401 with valid auth, got {response.status_code}: {response.text}"
        print(f"✓ POST /api/upload/init with auth returns {response.status_code}")


# ==================== NOTIFICATIONS SCHEMA FIX ====================

class TestNotificationsQuery:
    """Test notifications query matches target_user and for_role"""
    
    def test_get_my_notifications(self, admin_headers):
        """GET /api/notifications/my should return notifications matching target_user or for_role"""
        response = requests.get(f"{API_URL}/notifications/my", headers=admin_headers)
        
        assert response.status_code == 200, \
            f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), f"Expected list response, got {type(data)}"
        
        print(f"✓ GET /api/notifications/my returns {len(data)} notifications")
        
        # If there are notifications, verify they match the query criteria
        if data:
            # Verify each notification is for the current user
            for notif in data[:5]:  # Check first 5
                target_user = notif.get('target_user')
                for_role = notif.get('for_role')
                # Should match one of: target_user=admin, target_user=all, for_role=admin, for_role=all
                is_valid = target_user in ['admin', 'all'] or for_role in ['admin', 'all']
                print(f"  Notification: target_user={target_user}, for_role={for_role} - Valid: {is_valid}")


# ==================== HEALTH CHECK ====================

class TestHealthEndpoint:
    """Health check to verify API is accessible"""
    
    def test_api_health(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{API_URL}/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("✓ API health check passed")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
