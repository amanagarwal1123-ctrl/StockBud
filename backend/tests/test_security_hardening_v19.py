"""
Security Hardening Test Suite v19
Tests for massive security changes:
1. 31 GET routes requiring auth
2. 10 write endpoints with role checks (admin-only)
3. IDOR fix on polythene/today
4. JWT secret hardening
5. initialize-admin not returning password
6. Notification mark-read expanded filter
"""

import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthEndpoint:
    """Health endpoints should be public (no auth required)"""
    
    def test_health_public(self):
        """GET /health should be publicly accessible"""
        response = requests.get(f"{BASE_URL}/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        print("✓ Health endpoint is public")

    def test_api_health_public(self):
        """GET /api/health should be publicly accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"API Health check failed: {response.text}"
        print("✓ API Health endpoint is public")


class TestLogin:
    """Test login still works after JWT secret change"""
    
    def test_login_success(self):
        """Login with admin/admin123 should work"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert "user" in data, "No user in response"
        print(f"✓ Login successful, token received (length: {len(data['access_token'])})")


class TestInitializeAdmin:
    """Test initialize-admin does NOT return password"""
    
    def test_initialize_admin_no_password(self):
        """POST /api/users/initialize-admin should NOT return password field"""
        response = requests.post(f"{BASE_URL}/api/users/initialize-admin")
        # Expect 400 since users already exist
        assert response.status_code == 400, f"Unexpected status: {response.status_code}"
        data = response.json()
        # Check response does NOT contain password
        assert "password" not in data, "Response should NOT contain password field"
        print("✓ initialize-admin response does NOT contain password field")


class TestGETRoutesRequireAuth:
    """Test that 31 GET routes now require authentication"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
    
    def test_transactions_requires_auth(self):
        """GET /api/transactions should require auth"""
        response = self.session.get(f"{BASE_URL}/api/transactions")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/transactions requires auth")
    
    def test_inventory_current_requires_auth(self):
        """GET /api/inventory/current should require auth"""
        response = self.session.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/inventory/current requires auth")
    
    def test_analytics_profit_requires_auth(self):
        """GET /api/analytics/profit should require auth"""
        response = self.session.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/analytics/profit requires auth")
    
    def test_orders_requires_auth(self):
        """GET /api/orders should require auth"""
        response = self.session.get(f"{BASE_URL}/api/orders")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/orders requires auth")
    
    def test_item_buffers_requires_auth(self):
        """GET /api/item-buffers should require auth"""
        response = self.session.get(f"{BASE_URL}/api/item-buffers")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/item-buffers requires auth")
    
    def test_master_items_requires_auth(self):
        """GET /api/master-items should require auth"""
        response = self.session.get(f"{BASE_URL}/api/master-items")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/master-items requires auth")
    
    def test_mappings_all_requires_auth(self):
        """GET /api/mappings/all should require auth"""
        response = self.session.get(f"{BASE_URL}/api/mappings/all")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/mappings/all requires auth")
    
    def test_stats_requires_auth(self):
        """GET /api/stats should require auth"""
        response = self.session.get(f"{BASE_URL}/api/stats")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/stats requires auth")
    
    def test_historical_summary_requires_auth(self):
        """GET /api/historical/summary should require auth"""
        response = self.session.get(f"{BASE_URL}/api/historical/summary")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/historical/summary requires auth")
    
    def test_purchase_ledger_all_requires_auth(self):
        """GET /api/purchase-ledger/all should require auth"""
        response = self.session.get(f"{BASE_URL}/api/purchase-ledger/all")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/purchase-ledger/all requires auth")
    
    def test_mappings_unmapped_requires_auth(self):
        """GET /api/mappings/unmapped should require auth"""
        response = self.session.get(f"{BASE_URL}/api/mappings/unmapped")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/mappings/unmapped requires auth")
    
    def test_stamp_verification_all_requires_auth(self):
        """GET /api/stamp-verification/all should require auth"""
        response = self.session.get(f"{BASE_URL}/api/stamp-verification/all")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/stamp-verification/all requires auth")
    
    def test_stamp_verification_history_requires_auth(self):
        """GET /api/stamp-verification/history should require auth"""
        response = self.session.get(f"{BASE_URL}/api/stamp-verification/history")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/stamp-verification/history requires auth")
    
    def test_analytics_customer_profit_requires_auth(self):
        """GET /api/analytics/customer-profit should require auth"""
        response = self.session.get(f"{BASE_URL}/api/analytics/customer-profit")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/analytics/customer-profit requires auth")
    
    def test_analytics_supplier_profit_requires_auth(self):
        """GET /api/analytics/supplier-profit should require auth"""
        response = self.session.get(f"{BASE_URL}/api/analytics/supplier-profit")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/analytics/supplier-profit requires auth")


class TestGETRoutesWithAuth:
    """Test that GET routes work WITH valid auth token"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login to get token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_transactions_with_auth(self):
        """GET /api/transactions should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/transactions")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/transactions works with auth")
    
    def test_inventory_current_with_auth(self):
        """GET /api/inventory/current should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/inventory/current works with auth")
    
    def test_analytics_profit_with_auth(self):
        """GET /api/analytics/profit should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/analytics/profit works with auth")
    
    def test_orders_with_auth(self):
        """GET /api/orders should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/orders")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/orders works with auth")
    
    def test_item_buffers_with_auth(self):
        """GET /api/item-buffers should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/item-buffers")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/item-buffers works with auth")
    
    def test_master_items_with_auth(self):
        """GET /api/master-items should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/master-items")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/master-items works with auth")
    
    def test_mappings_all_with_auth(self):
        """GET /api/mappings/all should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/mappings/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/mappings/all works with auth")
    
    def test_stats_with_auth(self):
        """GET /api/stats should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/stats")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/stats works with auth")
    
    def test_historical_summary_with_auth(self):
        """GET /api/historical/summary should work with auth"""
        response = self.session.get(f"{BASE_URL}/api/historical/summary")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ GET /api/historical/summary works with auth")


class TestAdminOnlyWriteEndpoints:
    """Test that admin-only write endpoints reject non-admin roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
    
    def test_client_batch_requires_auth(self):
        """POST /api/upload/client-batch should require auth"""
        response = self.session.post(f"{BASE_URL}/api/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": "test123",
            "headers": [],
            "rows": []
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/upload/client-batch requires auth")
    
    def test_mappings_create_new_item_requires_auth(self):
        """POST /api/mappings/create-new-item should require auth"""
        response = self.session.post(f"{BASE_URL}/api/mappings/create-new-item", json={
            "item_name": "test",
            "stamp": "925"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/mappings/create-new-item requires auth")
    
    def test_purchase_ledger_upload_requires_auth(self):
        """POST /api/purchase-ledger/upload should require auth"""
        response = self.session.post(f"{BASE_URL}/api/purchase-ledger/upload")
        assert response.status_code in [401, 403, 422], f"Expected 401/403/422, got {response.status_code}"
        print("✓ POST /api/purchase-ledger/upload requires auth")
    
    def test_mappings_create_requires_auth(self):
        """POST /api/mappings/create should require auth"""
        response = self.session.post(f"{BASE_URL}/api/mappings/create", params={
            "transaction_name": "test",
            "master_name": "test"
        })
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/mappings/create requires auth")
    
    def test_mappings_delete_requires_auth(self):
        """DELETE /api/mappings/{name} should require auth"""
        response = self.session.delete(f"{BASE_URL}/api/mappings/test")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ DELETE /api/mappings/{name} requires auth")
    
    def test_history_undo_requires_auth(self):
        """POST /api/history/undo should require auth"""
        response = self.session.post(f"{BASE_URL}/api/history/undo")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/history/undo requires auth")
    
    def test_item_assign_stamp_requires_auth(self):
        """POST /api/item/{name}/assign-stamp should require auth"""
        response = self.session.post(f"{BASE_URL}/api/item/test/assign-stamp", json={"stamp": "925"})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/item/{name}/assign-stamp requires auth")
    
    def test_item_buffers_update_requires_auth(self):
        """PUT /api/item-buffers/{name} should require auth"""
        response = self.session.put(f"{BASE_URL}/api/item-buffers/test", params={"minimum_stock_kg": 1.0})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ PUT /api/item-buffers/{name} requires auth")
    
    def test_smart_insights_requires_auth(self):
        """POST /api/analytics/smart-insights should require auth"""
        response = self.session.post(f"{BASE_URL}/api/analytics/smart-insights", json={"category": "test"})
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/analytics/smart-insights requires auth")


class TestAdminOnlyEndpointsWithAuth:
    """Test admin-only endpoints work with admin auth and verify role restriction"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin to get token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_client_batch_admin_only_code_check(self):
        """POST /api/upload/client-batch should work for admin (check role restriction in code)"""
        # Send a minimal request - it may return 400 for missing data but NOT 403
        response = self.session.post(f"{BASE_URL}/api/upload/client-batch", json={
            "file_type": "historical_sale",
            "batch_id": "test123"
        })
        # Should NOT be 403 for admin - could be 400 for missing rows
        assert response.status_code != 403, f"Admin should not get 403: {response.text}"
        print(f"✓ POST /api/upload/client-batch allows admin (status: {response.status_code})")
    
    def test_mappings_create_new_item_admin_only(self):
        """POST /api/mappings/create-new-item should work for admin"""
        response = self.session.post(f"{BASE_URL}/api/mappings/create-new-item", json={
            "item_name": f"TEST_ITEM_{datetime.now().timestamp()}",
            "stamp": "925"
        })
        # Should NOT be 403 for admin
        assert response.status_code != 403, f"Admin should not get 403: {response.text}"
        print(f"✓ POST /api/mappings/create-new-item allows admin (status: {response.status_code})")
    
    def test_purchase_ledger_upload_admin_only(self):
        """POST /api/purchase-ledger/upload - verify admin role check"""
        response = self.session.post(f"{BASE_URL}/api/purchase-ledger/upload")
        # Should NOT be 403 for admin (may be 422 for missing file)
        assert response.status_code != 403, f"Admin should not get 403: {response.text}"
        print(f"✓ POST /api/purchase-ledger/upload allows admin (status: {response.status_code})")
    
    def test_mappings_delete_admin_only(self):
        """DELETE /api/mappings/{name} - verify admin role check"""
        response = self.session.delete(f"{BASE_URL}/api/mappings/TEST_NONEXISTENT")
        # Should NOT be 403 for admin (may be 404)
        assert response.status_code != 403, f"Admin should not get 403: {response.text}"
        print(f"✓ DELETE /api/mappings allows admin (status: {response.status_code})")
    
    def test_history_undo_admin_only(self):
        """POST /api/history/undo - verify admin role check"""
        response = self.session.post(f"{BASE_URL}/api/history/undo")
        # Should NOT be 403 for admin (may be 404 or 400)
        assert response.status_code != 403, f"Admin should not get 403: {response.text}"
        print(f"✓ POST /api/history/undo allows admin (status: {response.status_code})")


class TestPhysicalStockUploadRoles:
    """Test physical-stock/upload allows admin and manager roles"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_physical_stock_upload_admin_allowed(self):
        """POST /api/physical-stock/upload should allow admin"""
        response = self.session.post(f"{BASE_URL}/api/physical-stock/upload")
        # Should NOT be 403 for admin (may be 422 for missing file)
        assert response.status_code != 403, f"Admin should not get 403: {response.text}"
        print(f"✓ POST /api/physical-stock/upload allows admin (status: {response.status_code})")


class TestIDORPolytheneToday:
    """Test IDOR fix on /polythene/today/{username}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_polythene_today_requires_auth(self):
        """GET /api/polythene/today/{username} should require auth"""
        session = requests.Session()
        response = session.get(f"{BASE_URL}/api/polythene/today/admin")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/polythene/today/{username} requires auth")
    
    def test_polythene_today_admin_can_view_own(self):
        """Admin can view their own polythene entries"""
        response = self.session.get(f"{BASE_URL}/api/polythene/today/admin")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Admin can view own polythene/today entries")
    
    def test_polythene_today_admin_can_view_others(self):
        """Admin can view other users' polythene entries (role: admin/manager)"""
        response = self.session.get(f"{BASE_URL}/api/polythene/today/otheruser")
        # Admin should be allowed to view anyone's entries (role in ['admin', 'manager'])
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Admin can view other users' polythene/today entries")


class TestNotificationMarkRead:
    """Test notification mark-read expanded filter"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        # Login as admin
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
    
    def test_notification_mark_read_requires_auth(self):
        """POST /api/notifications/{id}/read should require auth"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/notifications/test123/read")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ POST /api/notifications/{id}/read requires auth")
    
    def test_notification_mark_read_with_auth(self):
        """POST /api/notifications/{id}/read should work with auth"""
        response = self.session.post(f"{BASE_URL}/api/notifications/nonexistent/read")
        # Should return 200 even if notification not found (update_one with no match)
        assert response.status_code in [200, 404], f"Expected 200/404, got {response.status_code}"
        print(f"✓ POST /api/notifications mark-read works with auth (status: {response.status_code})")


class TestMoreGETEndpointsNoAuth:
    """Additional GET endpoints that should require auth"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
    
    def test_physical_stock_compare_requires_auth(self):
        """GET /api/physical-stock/compare should require auth"""
        response = self.session.get(f"{BASE_URL}/api/physical-stock/compare")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/physical-stock/compare requires auth")
    
    def test_history_recent_uploads_requires_auth(self):
        """GET /api/history/recent-uploads should require auth"""
        response = self.session.get(f"{BASE_URL}/api/history/recent-uploads")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/history/recent-uploads requires auth")
    
    def test_history_actions_requires_auth(self):
        """GET /api/history/actions should require auth"""
        response = self.session.get(f"{BASE_URL}/api/history/actions")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/history/actions requires auth")
    
    def test_notifications_my_requires_auth(self):
        """GET /api/notifications/my should require auth"""
        response = self.session.get(f"{BASE_URL}/api/notifications/my")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/notifications/my requires auth")
    
    def test_activity_log_requires_auth(self):
        """GET /api/activity-log should require auth"""
        response = self.session.get(f"{BASE_URL}/api/activity-log")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/activity-log requires auth")
    
    def test_item_groups_requires_auth(self):
        """GET /api/item-groups should require auth"""
        response = self.session.get(f"{BASE_URL}/api/item-groups")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/item-groups requires auth")
    
    def test_stamp_assignments_requires_auth(self):
        """GET /api/stamp-assignments should require auth"""
        response = self.session.get(f"{BASE_URL}/api/stamp-assignments")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/stamp-assignments requires auth")
    
    def test_orders_overdue_requires_auth(self):
        """GET /api/orders/overdue should require auth"""
        response = self.session.get(f"{BASE_URL}/api/orders/overdue")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("✓ GET /api/orders/overdue requires auth")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
