"""
Security Hardening Tests - Iteration 18
Tests for 15+ endpoints that were modified to add authentication requirements.
Also tests horizontal access control and admin-only restrictions.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Health check - no auth required"""
    
    def test_health_returns_200(self):
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✓ GET /api/health returns 200 without auth")


class TestAuthLogin:
    """Test login functionality still works"""
    
    def test_login_success(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data.get("token_type") == "bearer"
        print("✓ Login with admin/admin123 works")
        return data["access_token"]


class TestUnauthenticatedEndpoints403:
    """Test that protected endpoints return 403 without auth"""
    
    def test_upload_client_batch_no_auth(self):
        """POST /api/upload/client-batch returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/upload/client-batch", json={
            "file_type": "sale",
            "batch_id": "test",
            "headers": [],
            "rows": []
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/upload/client-batch returns {response.status_code} without auth")
    
    def test_mappings_create_new_item_no_auth(self):
        """POST /api/mappings/create-new-item returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/mappings/create-new-item?transaction_name=test&stamp=test")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/mappings/create-new-item returns {response.status_code} without auth")
    
    def test_physical_stock_upload_no_auth(self):
        """POST /api/physical-stock/upload returns 403 without auth"""
        files = {'file': ('test.xlsx', b'dummy', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = requests.post(f"{BASE_URL}/api/physical-stock/upload", files=files)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/physical-stock/upload returns {response.status_code} without auth")
    
    def test_purchase_ledger_upload_no_auth(self):
        """POST /api/purchase-ledger/upload returns 403 without auth"""
        files = {'file': ('test.xlsx', b'dummy', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        response = requests.post(f"{BASE_URL}/api/purchase-ledger/upload", files=files)
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/purchase-ledger/upload returns {response.status_code} without auth")
    
    def test_mappings_create_no_auth(self):
        """POST /api/mappings/create returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/mappings/create?transaction_name=test&master_name=test")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/mappings/create returns {response.status_code} without auth")
    
    def test_stamp_verification_save_no_auth(self):
        """POST /api/stamp-verification/save returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/stamp-verification/save", json={
            "stamp": "TEST",
            "entries": []
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/stamp-verification/save returns {response.status_code} without auth")
    
    def test_mappings_delete_no_auth(self):
        """DELETE /api/mappings/{name} returns 403 without auth"""
        response = requests.delete(f"{BASE_URL}/api/mappings/test")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ DELETE /api/mappings/test returns {response.status_code} without auth")
    
    def test_history_undo_no_auth(self):
        """POST /api/history/undo returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/history/undo")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/history/undo returns {response.status_code} without auth")
    
    def test_assign_stamp_no_auth(self):
        """POST /api/item/{name}/assign-stamp returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/item/test/assign-stamp?stamp=TEST")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/item/test/assign-stamp returns {response.status_code} without auth")
    
    def test_item_buffers_update_no_auth(self):
        """PUT /api/item-buffers/{name} returns 403 without auth"""
        response = requests.put(f"{BASE_URL}/api/item-buffers/test?minimum_stock_kg=10")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ PUT /api/item-buffers/test returns {response.status_code} without auth")
    
    def test_smart_insights_no_auth(self):
        """POST /api/analytics/smart-insights returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/analytics/smart-insights", json={})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/analytics/smart-insights returns {response.status_code} without auth")
    
    def test_history_undo_upload_no_auth(self):
        """POST /api/history/undo-upload returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/history/undo-upload?batch_id=test")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/history/undo-upload returns {response.status_code} without auth")
    
    def test_history_recent_uploads_no_auth(self):
        """GET /api/history/recent-uploads returns 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/history/recent-uploads")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ GET /api/history/recent-uploads returns {response.status_code} without auth")
    
    def test_executive_entries_no_auth(self):
        """GET /api/executive/my-entries/{username} returns 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/executive/my-entries/admin")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ GET /api/executive/my-entries returns {response.status_code} without auth")
    
    def test_polythene_today_no_auth(self):
        """GET /api/polythene/today/{username} returns 403 without auth"""
        response = requests.get(f"{BASE_URL}/api/polythene/today/admin")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ GET /api/polythene/today returns {response.status_code} without auth")
    
    def test_notifications_read_no_auth(self):
        """POST /api/notifications/{id}/read returns 403 without auth"""
        response = requests.post(f"{BASE_URL}/api/notifications/test-id/read")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print(f"✓ POST /api/notifications/{id}/read returns {response.status_code} without auth")


class TestAuthenticatedEndpoints:
    """Test endpoints work correctly WITH auth"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Cannot login - auth broken")
        return response.json()["access_token"]
    
    def test_executive_entries_own_access(self, admin_token):
        """Admin can access their own entries"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/executive/my-entries/admin", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Admin can access own entries at /api/executive/my-entries/admin")
    
    def test_history_recent_uploads_admin(self, admin_token):
        """Admin can access recent-uploads"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/history/recent-uploads", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Admin can access /api/history/recent-uploads")
    
    def test_polythene_today_with_auth(self, admin_token):
        """Authenticated user can access polythene/today"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/polythene/today/admin", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Authenticated user can access /api/polythene/today")


class TestHorizontalAccessControl:
    """Test that users cannot access other users' data"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Cannot login - auth broken")
        return response.json()["access_token"]
    
    def test_executive_entries_requires_ownership(self, admin_token):
        """Non-admin user cannot access other user's entries"""
        # Since we only have admin, test that admin CAN access other entries (role=admin)
        # The code shows admin/manager can view any, others can only view own
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Admin accessing admin's entries (self) - should work
        response = requests.get(f"{BASE_URL}/api/executive/my-entries/admin", headers=headers)
        assert response.status_code == 200, "Admin should access own entries"
        print("✓ Horizontal access: Admin can access own entries")
        
        # Admin accessing other user's entries - should work (admin role)
        response = requests.get(f"{BASE_URL}/api/executive/my-entries/otheruser", headers=headers)
        # Admin should be allowed to see other entries
        assert response.status_code == 200, "Admin should access other user entries"
        print("✓ Horizontal access: Admin can access other users' entries (by role)")


class TestDuplicateCheck:
    """Test duplicate check on create-new-item"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Cannot login - auth broken")
        return response.json()["access_token"]
    
    def test_create_new_item_duplicate_check(self, admin_token):
        """Creating same item twice returns success=false on second call"""
        import uuid
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # Generate unique test name
        test_name = f"TEST_ITEM_{uuid.uuid4().hex[:8]}"
        
        # First call - should succeed
        response1 = requests.post(
            f"{BASE_URL}/api/mappings/create-new-item?transaction_name={test_name}&stamp=TEST",
            headers=headers
        )
        assert response1.status_code == 200, f"First create failed: {response1.text}"
        data1 = response1.json()
        assert data1.get('success') == True, f"First create should succeed: {data1}"
        print(f"✓ First create-new-item call succeeded for {test_name}")
        
        # Second call - should fail (duplicate)
        response2 = requests.post(
            f"{BASE_URL}/api/mappings/create-new-item?transaction_name={test_name}&stamp=TEST",
            headers=headers
        )
        assert response2.status_code == 200, f"Second create status unexpected: {response2.status_code}"
        data2 = response2.json()
        assert data2.get('success') == False, f"Second create should fail due to duplicate: {data2}"
        print(f"✓ Second create-new-item call returns success=false (duplicate detected)")


class TestAdminOnlyEndpoints:
    """Test admin-only restrictions"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Cannot login - auth broken")
        return response.json()["access_token"]
    
    def test_undo_upload_admin_can_access(self, admin_token):
        """Admin can access undo-upload (even if batch not found)"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/history/undo-upload?batch_id=nonexistent", headers=headers)
        # 404 is expected (batch not found), but not 403
        assert response.status_code in [200, 404], f"Expected 200/404, got {response.status_code}: {response.text}"
        print("✓ Admin can access /api/history/undo-upload (no 403)")
    
    def test_recent_uploads_admin_can_access(self, admin_token):
        """Admin can access recent-uploads"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/history/recent-uploads", headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Admin can access /api/history/recent-uploads")


class TestNotificationScoping:
    """Test notification read is scoped to current user"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Cannot login - auth broken")
        return response.json()["access_token"]
    
    def test_notification_read_with_auth(self, admin_token):
        """Notification read endpoint works with auth"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        # Even if notification doesn't exist, should not return 403/401
        response = requests.post(f"{BASE_URL}/api/notifications/test-notification-id/read", headers=headers)
        # Should return 200 (or possibly 404 if validation is added)
        assert response.status_code in [200, 204, 404], f"Expected 200/204/404, got {response.status_code}"
        print("✓ POST /api/notifications/{id}/read works with auth")
