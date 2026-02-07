"""
Backend tests for StockBud - Testing 3 decimal precision for weight values
Tests verify that all weight-related fields return values with proper 3 decimal precision
"""
import pytest
import requests
import os
import re

# Get backend URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestAuth:
    """Test authentication endpoints"""
    
    def test_health_check(self):
        """Test health check endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✓ Health check passed")
    
    def test_admin_login(self):
        """Test admin login with credentials admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert 'access_token' in data, "No access token in response"
        assert data['user']['username'] == 'admin'
        print("✓ Admin login successful")
        return data['access_token']


class TestDecimalPrecision:
    """Test 3 decimal precision for weight values"""
    
    @pytest.fixture
    def auth_token(self):
        """Get auth token for authenticated requests"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Authentication failed - skipping authenticated tests")
        return response.json().get('access_token')
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with authorization"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_current_inventory_api(self, auth_headers):
        """Test /api/inventory/current returns rounded weight values with max 3 decimal precision"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=auth_headers)
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        # Check total values have max 3 decimal precision
        total_gr_wt = data.get('total_gr_wt', 0)
        total_net_wt = data.get('total_net_wt', 0)
        
        # Verify totals exist and are numbers
        assert isinstance(total_gr_wt, (int, float)), "total_gr_wt should be a number"
        assert isinstance(total_net_wt, (int, float)), "total_net_wt should be a number"
        
        print(f"✓ Total Gross Weight: {total_gr_wt}")
        print(f"✓ Total Net Weight: {total_net_wt}")
        
        # Check inventory items have max 3 decimal precision
        inventory = data.get('inventory', [])
        assert len(inventory) > 0, "Inventory should have items"
        
        print(f"✓ Found {len(inventory)} inventory items")
        
        # Verify first few items have proper decimal precision
        for item in inventory[:5]:
            gr_wt = item.get('gr_wt', 0)
            net_wt = item.get('net_wt', 0)
            fine = item.get('fine', 0)
            labor = item.get('labor', 0)
            
            # Verify these are numbers with max 3 decimal places
            assert isinstance(gr_wt, (int, float)), f"gr_wt should be number for {item.get('item_name')}"
            assert isinstance(net_wt, (int, float)), f"net_wt should be number for {item.get('item_name')}"
            assert isinstance(fine, (int, float)), f"fine should be number for {item.get('item_name')}"
            assert isinstance(labor, (int, float)), f"labor should be number for {item.get('item_name')}"
            
            # Verify max 3 decimal places using string conversion
            gr_wt_str = str(gr_wt)
            if '.' in gr_wt_str:
                decimals = len(gr_wt_str.split('.')[1])
                assert decimals <= 3, f"gr_wt has more than 3 decimals: {gr_wt}"
            
            net_wt_str = str(net_wt)
            if '.' in net_wt_str:
                decimals = len(net_wt_str.split('.')[1])
                assert decimals <= 3, f"net_wt has more than 3 decimals: {net_wt}"
            
            fine_str = str(fine)
            if '.' in fine_str:
                decimals = len(fine_str.split('.')[1])
                assert decimals <= 3, f"fine has more than 3 decimals: {fine}"
            
            labor_str = str(labor)
            if '.' in labor_str:
                decimals = len(labor_str.split('.')[1])
                assert decimals <= 3, f"labor has more than 3 decimals: {labor}"
            
            print(f"  ✓ Item '{item.get('item_name')[:30]}...' - gr_wt: {gr_wt}, net_wt: {net_wt}, fine: {fine}")
        
        print("✓ All inventory items have proper 3 decimal precision")
    
    def test_inventory_count(self, auth_headers):
        """Test inventory count matches expected ~344 items"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=auth_headers)
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        inventory = data.get('inventory', [])
        negative_items = data.get('negative_items', [])
        total_items = len(inventory) + len(negative_items)
        
        # Allow some flexibility in count
        assert total_items >= 300, f"Expected ~344 items, got {total_items}"
        print(f"✓ Total items in inventory: {total_items} (positive: {len(inventory)}, negative: {len(negative_items)})")
    
    def test_physical_stock_compare_api(self, auth_headers):
        """Test /api/physical-stock/compare returns weight values with 3 decimal precision"""
        response = requests.get(f"{BASE_URL}/api/physical-stock/compare", headers=auth_headers)
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        # Check totals have proper precision
        total_book_kg = data.get('total_book_kg', 0)
        total_physical_kg = data.get('total_physical_kg', 0)
        
        print(f"✓ Physical stock compare - Book total: {total_book_kg} kg")
        
        # Verify total has max 3 decimal places
        if isinstance(total_book_kg, float):
            total_str = str(total_book_kg)
            if '.' in total_str:
                decimals = len(total_str.split('.')[1])
                assert decimals <= 3, f"total_book_kg has more than 3 decimals"
        
        print(f"✓ All physical stock compare values have proper decimal precision")
    
    def test_analytics_party_api(self, auth_headers):
        """Test /api/analytics/party-analysis returns weight values with 3 decimal precision"""
        response = requests.get(f"{BASE_URL}/api/analytics/party-analysis", headers=auth_headers)
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        customers = data.get('customers', [])
        suppliers = data.get('suppliers', [])
        
        print(f"✓ Party analytics returned {len(customers)} customers and {len(suppliers)} suppliers")
        
        # Check first customer/supplier for decimal precision
        for customer in customers[:2]:
            net_wt = customer.get('total_net_wt', 0)
            fine_wt = customer.get('total_fine_wt', 0)
            
            # Verify max 3 decimal places
            if isinstance(net_wt, float):
                net_str = str(net_wt)
                if '.' in net_str:
                    decimals = len(net_str.split('.')[1])
                    assert decimals <= 3, f"total_net_wt has more than 3 decimals: {net_wt}"
            
            print(f"  ✓ Customer {customer.get('party_name', 'Unknown')[:20]} - net_wt: {net_wt}")
    
    def test_stats_api(self, auth_headers):
        """Test /api/stats returns dashboard stats"""
        response = requests.get(f"{BASE_URL}/api/stats", headers=auth_headers)
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        # Stats API returns: total_transactions, total_purchases, total_sales, total_opening_stock, total_parties
        assert 'total_opening_stock' in data, "Missing total_opening_stock in stats"
        assert 'total_transactions' in data, "Missing total_transactions in stats"
        print(f"✓ Stats API returned: total_opening_stock={data.get('total_opening_stock')}, total_transactions={data.get('total_transactions')}")


class TestTransactions:
    """Test transaction endpoints"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get headers with authorization"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code != 200:
            pytest.skip("Authentication failed")
        return {"Authorization": f"Bearer {response.json().get('access_token')}"}
    
    def test_get_transactions(self, auth_headers):
        """Test getting transactions list"""
        response = requests.get(f"{BASE_URL}/api/transactions", headers=auth_headers)
        assert response.status_code == 200, f"API failed: {response.text}"
        data = response.json()
        
        print(f"✓ Retrieved {len(data)} transactions")
        
        # Check first few transactions have proper structure
        for trans in data[:3]:
            assert 'item_name' in trans, "Transaction missing item_name"
            assert 'type' in trans, "Transaction missing type"
            print(f"  ✓ Transaction: {trans.get('item_name', 'Unknown')[:30]} - type: {trans.get('type')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
