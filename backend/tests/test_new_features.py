"""
Test new StockBud features:
1. Item Buffer Management - /api/item-buffers/categorize, /api/item-buffers, PUT /api/item-buffers/{item_name}
2. Order Management - /api/orders/create, /api/orders, PUT /api/orders/{id}/received  
3. Data Visualization - /api/analytics/visualization
4. Stamp Assignments - /api/stamp-assignments
5. Categorized Notifications - /api/notifications/categorized
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with authentication"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestAuthentication:
    """Test login endpoint"""
    
    def test_admin_login_success(self):
        """Login as admin with correct credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
    
    def test_login_invalid_credentials(self):
        """Login with wrong credentials fails"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401


class TestItemBufferManagement:
    """Test Item Buffer endpoints - categorize items into movement tiers"""
    
    def test_categorize_items_admin_only(self, auth_headers):
        """POST /api/item-buffers/categorize - categorize all items into 5 tiers"""
        response = requests.post(f"{BASE_URL}/api/item-buffers/categorize", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "success" in data
        assert data["success"] == True
        assert "total_items" in data
        assert "tiers" in data
        
        # Verify 5 tiers exist
        valid_tiers = ['fastest', 'fast', 'medium', 'slow', 'dead']
        for tier in data.get("tiers", {}):
            assert tier in valid_tiers, f"Unknown tier: {tier}"
        
        print(f"Categorized {data['total_items']} items into tiers: {data['tiers']}")
    
    def test_get_item_buffers(self):
        """GET /api/item-buffers - returns items with tier, velocity, status"""
        response = requests.get(f"{BASE_URL}/api/item-buffers")
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        
        # Check item structure
        if data["items"]:
            item = data["items"][0]
            required_fields = ['item_name', 'stamp', 'tier', 'tier_num', 
                              'monthly_velocity_kg', 'current_stock_kg', 
                              'minimum_stock_kg', 'lower_buffer_kg', 
                              'upper_buffer_kg', 'status']
            for field in required_fields:
                assert field in item, f"Missing field: {field}"
            
            # Verify status is valid color
            assert item['status'] in ['red', 'green', 'yellow'], f"Invalid status: {item['status']}"
            
            # Verify tier is valid
            assert item['tier'] in ['fastest', 'fast', 'medium', 'slow', 'dead']
        
        print(f"Got {data['total']} item buffers")
    
    def test_get_item_buffers_filter_by_tier(self):
        """GET /api/item-buffers?tier=dead - filter by tier"""
        response = requests.get(f"{BASE_URL}/api/item-buffers?tier=dead")
        assert response.status_code == 200
        data = response.json()
        
        # All items should be dead tier
        for item in data.get("items", []):
            assert item['tier'] == 'dead'
    
    def test_get_item_buffers_filter_by_status(self):
        """GET /api/item-buffers?status=red - filter by status"""
        response = requests.get(f"{BASE_URL}/api/item-buffers?status=red")
        assert response.status_code == 200
        data = response.json()
        
        # All items should have red status
        for item in data.get("items", []):
            assert item['status'] == 'red'
    
    def test_update_minimum_stock(self):
        """PUT /api/item-buffers/{item_name} - update minimum stock"""
        # First get an item name
        buffers = requests.get(f"{BASE_URL}/api/item-buffers").json()
        if not buffers.get("items"):
            pytest.skip("No items in buffers")
        
        test_item = buffers["items"][0]["item_name"]
        new_min = 5.5
        
        response = requests.put(
            f"{BASE_URL}/api/item-buffers/{requests.utils.quote(test_item, safe='')}",
            params={"minimum_stock_kg": new_min}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify update
        updated = requests.get(f"{BASE_URL}/api/item-buffers").json()
        updated_item = next((i for i in updated["items"] if i["item_name"] == test_item), None)
        assert updated_item is not None
        assert updated_item["minimum_stock_kg"] == new_min
        
        print(f"Updated minimum stock for '{test_item}' to {new_min} kg")


class TestOrderManagement:
    """Test Order Management endpoints"""
    
    def test_get_orders(self):
        """GET /api/orders - returns orders list"""
        response = requests.get(f"{BASE_URL}/api/orders")
        assert response.status_code == 200
        data = response.json()
        
        assert "orders" in data
        print(f"Got {len(data['orders'])} orders")
    
    def test_create_order(self, auth_headers):
        """POST /api/orders/create - create restock order"""
        # First get an item from buffers
        buffers = requests.get(f"{BASE_URL}/api/item-buffers").json()
        if not buffers.get("items"):
            pytest.skip("No items in buffers")
        
        test_item = buffers["items"][0]["item_name"]
        
        order_data = {
            "item_name": f"TEST_{test_item[:20]}",
            "quantity_kg": 10.5,
            "supplier": "Test Supplier Co",
            "notes": "Test order from pytest"
        }
        
        response = requests.post(f"{BASE_URL}/api/orders/create", json=order_data, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "order_id" in data
        
        # Verify order appears in list
        orders = requests.get(f"{BASE_URL}/api/orders").json()
        test_order = next((o for o in orders["orders"] if o["id"] == data["order_id"]), None)
        assert test_order is not None
        assert test_order["item_name"] == order_data["item_name"]
        assert test_order["quantity_kg"] == order_data["quantity_kg"]
        assert test_order["status"] == "ordered"
        
        print(f"Created order {data['order_id']} for {order_data['item_name']}")
        return data["order_id"]
    
    def test_mark_order_received(self, auth_headers):
        """PUT /api/orders/{order_id}/received - mark order as received"""
        # Create a test order first
        order_data = {
            "item_name": "TEST_RECEIVE_ORDER",
            "quantity_kg": 5.0,
            "supplier": "Test",
            "notes": "Test receive"
        }
        create_resp = requests.post(f"{BASE_URL}/api/orders/create", json=order_data, headers=auth_headers)
        assert create_resp.status_code == 200
        order_id = create_resp.json()["order_id"]
        
        # Mark as received
        response = requests.put(f"{BASE_URL}/api/orders/{order_id}/received", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify status changed
        orders = requests.get(f"{BASE_URL}/api/orders").json()
        updated_order = next((o for o in orders["orders"] if o["id"] == order_id), None)
        assert updated_order is not None
        assert updated_order["status"] == "received"
        
        print(f"Order {order_id} marked as received")
    
    def test_get_orders_filtered_by_status(self):
        """GET /api/orders?status=ordered - filter by status"""
        response = requests.get(f"{BASE_URL}/api/orders?status=ordered")
        assert response.status_code == 200
        data = response.json()
        
        for order in data.get("orders", []):
            assert order["status"] == "ordered"


class TestDataVisualization:
    """Test Data Visualization endpoints"""
    
    def test_get_visualization_data(self):
        """GET /api/analytics/visualization - returns chart data"""
        response = requests.get(f"{BASE_URL}/api/analytics/visualization")
        assert response.status_code == 200
        data = response.json()
        
        # Verify all required chart data sections exist
        required_sections = [
            'sales_by_item',
            'sales_by_party', 
            'purchases_by_supplier',
            'tier_distribution',
            'sales_trend',
            'stock_health'
        ]
        
        for section in required_sections:
            assert section in data, f"Missing section: {section}"
        
        # Verify stock_health has correct structure
        health = data['stock_health']
        assert 'red' in health
        assert 'green' in health
        assert 'yellow' in health
        
        print(f"Visualization data retrieved: {len(data['sales_by_item'])} items by sales, stock health: {health}")
    
    def test_get_visualization_with_date_filter(self):
        """GET /api/analytics/visualization with date range"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/visualization",
            params={"start_date": "2025-01-01", "end_date": "2025-12-31"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return same structure even with filters
        assert 'sales_by_item' in data
        assert 'stock_health' in data


class TestStampAssignments:
    """Test Stamp-User Assignment endpoints"""
    
    def test_get_stamp_assignments(self):
        """GET /api/stamp-assignments - returns assignments list"""
        response = requests.get(f"{BASE_URL}/api/stamp-assignments")
        assert response.status_code == 200
        data = response.json()
        
        assert "assignments" in data
        print(f"Got {len(data['assignments'])} stamp assignments")
    
    def test_create_stamp_assignment(self, auth_headers):
        """POST /api/stamp-assignments - assign user to stamp"""
        assignment_data = {
            "stamp": "STAMP 1",
            "assigned_user": "admin"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/stamp-assignments", 
            json=assignment_data, 
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify assignment exists
        assignments = requests.get(f"{BASE_URL}/api/stamp-assignments").json()
        test_assign = next((a for a in assignments["assignments"] if a["stamp"] == "STAMP 1"), None)
        assert test_assign is not None
        assert test_assign["assigned_user"] == "admin"
        
        print(f"Assigned admin to STAMP 1")
    
    def test_delete_stamp_assignment(self, auth_headers):
        """DELETE /api/stamp-assignments/{stamp} - remove assignment"""
        # First create an assignment
        assignment_data = {"stamp": "STAMP 99", "assigned_user": "admin"}
        requests.post(f"{BASE_URL}/api/stamp-assignments", json=assignment_data, headers=auth_headers)
        
        # Delete it
        response = requests.delete(
            f"{BASE_URL}/api/stamp-assignments/{requests.utils.quote('STAMP 99', safe='')}",
            headers=auth_headers
        )
        assert response.status_code == 200


class TestCategorizedNotifications:
    """Test enhanced notifications endpoint"""
    
    def test_get_categorized_notifications(self, auth_headers):
        """GET /api/notifications/categorized - returns organized notifications"""
        response = requests.get(f"{BASE_URL}/api/notifications/categorized", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "notifications" in data
        assert "total_unread" in data
        
        # Verify categories exist
        categories = data["notifications"]
        expected_categories = ['stock', 'order', 'stamp', 'polythene', 'general']
        for cat in expected_categories:
            assert cat in categories, f"Missing category: {cat}"
        
        print(f"Got categorized notifications: total unread = {data['total_unread']}")
    
    def test_check_stock_alerts(self, auth_headers):
        """POST /api/notifications/check-stock-alerts - generate stock alerts"""
        response = requests.post(f"{BASE_URL}/api/notifications/check-stock-alerts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        print(f"Stock alerts: {data}")


class TestMasterItems:
    """Test master items endpoint (used by stamp assignments)"""
    
    def test_get_master_items(self):
        """GET /api/master-items - returns master item list"""
        response = requests.get(f"{BASE_URL}/api/master-items")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if data:
            item = data[0]
            assert "item_name" in item
            assert "stamp" in item
        
        print(f"Got {len(data)} master items")


class TestAISmartInsights:
    """Test AI Smart Analytics endpoint (may fail due to API limits)"""
    
    def test_smart_insights_endpoint_exists(self):
        """POST /api/analytics/smart-insights - endpoint exists"""
        # Just test endpoint exists, don't require success due to AI API limits
        response = requests.post(f"{BASE_URL}/api/analytics/smart-insights", json={
            "question": "What are the top selling items?"
        })
        # Accept 200 (success) or 500 (API key issue) as valid
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = response.json()
            assert "insights" in data
            print("AI insights working!")
        else:
            print("AI endpoint exists but failed (expected if API key has limits)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
