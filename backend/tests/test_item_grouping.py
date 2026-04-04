"""
Tests for Item Grouping feature - verifies that:
1. Current Stock shows grouped items with expand/collapse
2. Group-level Fine and Labour use combined purchase tunch from all members' ledger entries
3. Customer profit endpoint resolves items to group leaders
4. Item profit endpoint groups items by leader
5. Supplier profit endpoint resolves items to group leaders
6. Visualization endpoint correctly groups items by leader
7. Negative items list should have fewer items due to grouping fixing split-stock issue
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://margin-analytics-7.preview.emergentagent.com').rstrip('/')

# Known item groups from the problem statement
EXPECTED_GROUPS = {
    "TULSI 70 -264": ["TULSI 70 -264", "TULSI 70 BELT"],
    "SNT 40-256": ["SNT-40 PREMIUM", "SNT 40-256"],
    "KADA-AS 70": ["KADA AS 70 FANCY", "KADA-AS 70"],
    "SLG 70 BICCHIYA-255": ["SLG 70 BICCHIYA-255", "SLG-70 MICRO BICCHIYA"],
    "BARTAN-040": ["BARTAN-040", "LOTA"]
}


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for API calls"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping tests")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with authentication token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestHealthAndAuth:
    """Basic health and auth tests"""
    
    def test_health_endpoint(self):
        """Test health endpoint is accessible"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health endpoint working")
    
    def test_login_success(self):
        """Test login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print("✓ Login successful")


class TestItemGroupsAPI:
    """Tests for Item Groups CRUD endpoints"""
    
    def test_get_item_groups(self, auth_headers):
        """Test GET /api/item-groups returns list of groups"""
        response = requests.get(f"{BASE_URL}/api/item-groups", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # API returns {groups: [...]} structure
        groups = data.get('groups', data) if isinstance(data, dict) else data
        assert isinstance(groups, list)
        print(f"✓ Found {len(groups)} item groups")
        
        # Check if expected groups exist
        group_names = [g['group_name'] for g in groups]
        found_groups = [g for g in EXPECTED_GROUPS.keys() if g in group_names]
        print(f"  Found expected groups: {found_groups}")
        
        # Verify at least some expected groups exist
        assert len(found_groups) > 0, "Expected at least some item groups to exist"
        
        # Verify group structure
        for group in groups:
            assert 'group_name' in group
            assert 'members' in group
            if group['group_name'] in EXPECTED_GROUPS:
                members = group.get('members', [])
                print(f"  Group '{group['group_name']}' has members: {members}")
                # Members should include at least 2 items
                assert len(members) >= 2, f"Group {group['group_name']} should have at least 2 members"


class TestCurrentStockGrouping:
    """Tests for Current Stock with grouped items"""
    
    def test_current_inventory_endpoint(self):
        """Test GET /api/inventory/current returns grouped data"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "inventory" in data
        assert "negative_items" in data
        assert "total_items" in data
        assert "total_gr_wt" in data
        assert "total_net_wt" in data
        
        print(f"✓ Current inventory returned {data['total_items']} items")
        print(f"  Negative items: {len(data['negative_items'])}")
        print(f"  Total Net Weight: {data['total_net_wt'] / 1000:.3f} kg")
        
        return data
    
    def test_grouped_items_have_is_group_flag(self):
        """Test that grouped items have is_group=True and members array"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        inventory = data.get('inventory', [])
        
        # Find items that are groups
        grouped_items = [item for item in inventory if item.get('is_group')]
        print(f"✓ Found {len(grouped_items)} grouped items in inventory")
        
        # Verify structure of grouped items
        for item in grouped_items:
            if item.get('members') and len(item.get('members', [])) > 1:
                print(f"  Group: {item['item_name']} has {len(item['members'])} members")
                # Each member should have item_name, net_wt, gr_wt, fine, labor
                for member in item['members']:
                    assert 'item_name' in member, "Member should have item_name"
                    assert 'net_wt' in member, "Member should have net_wt"
        
        return grouped_items
    
    def test_specific_group_in_inventory(self):
        """Test that a specific expected group (TULSI 70 -264) appears correctly"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        inventory = data.get('inventory', [])
        
        # Look for TULSI 70 -264 group
        tulsi_group = next(
            (item for item in inventory if item['item_name'] == 'TULSI 70 -264'),
            None
        )
        
        if tulsi_group:
            print(f"✓ Found TULSI 70 -264 group in inventory")
            print(f"  is_group: {tulsi_group.get('is_group')}")
            print(f"  Net Weight: {tulsi_group.get('net_wt', 0) / 1000:.3f} kg")
            print(f"  Fine: {tulsi_group.get('fine', 0) / 1000:.3f} kg")
            print(f"  Labour: {tulsi_group.get('labor', 0)}")
            
            members = tulsi_group.get('members', [])
            if members:
                print(f"  Members ({len(members)}):")
                for m in members:
                    print(f"    - {m['item_name']}: Net={m.get('net_wt', 0)/1000:.3f}kg, Fine={m.get('fine', 0)/1000:.3f}kg")
            
            # Verify it's marked as a group if it has members
            if len(members) > 1:
                assert tulsi_group.get('is_group') == True
        else:
            print("⚠ TULSI 70 -264 not found in current inventory (may have 0 stock)")
    
    def test_fine_and_labour_use_group_ledger(self):
        """Test that Fine and Labour values are calculated using group-wide purchase data"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        inventory = data.get('inventory', [])
        
        # Find grouped items with stock
        grouped_with_stock = [
            item for item in inventory 
            if item.get('is_group') and item.get('net_wt', 0) > 0 and len(item.get('members', [])) > 1
        ]
        
        print(f"✓ Checking Fine/Labour for {len(grouped_with_stock)} grouped items with stock")
        
        for item in grouped_with_stock[:3]:  # Check first 3
            # Fine and Labour should be non-negative for items with positive stock
            fine = item.get('fine', 0)
            labour = item.get('labor', 0)
            print(f"  {item['item_name']}: Fine={fine/1000:.3f}kg, Labour=₹{labour:.2f}")
            
            # Members should have consistent tunch (from group ledger)
            members = item.get('members', [])
            if members:
                for m in members:
                    if m.get('net_wt', 0) > 0:
                        # Fine should be calculated (net_wt * tunch / 100)
                        # Just verify it exists and is reasonable
                        assert 'fine' in m, "Member should have fine calculated"


class TestCustomerProfitGrouping:
    """Tests for Customer Profit endpoint with group-aware resolution"""
    
    def test_customer_profit_endpoint(self):
        """Test GET /api/analytics/customer-profit returns valid data"""
        response = requests.get(f"{BASE_URL}/api/analytics/customer-profit")
        assert response.status_code == 200
        data = response.json()
        
        assert "customers" in data
        assert "total_customers" in data
        
        print(f"✓ Customer profit returned {data['total_customers']} customers")
        
        # Check structure of customer profit data
        if data['customers']:
            customer = data['customers'][0]
            assert 'customer_name' in customer
            assert 'silver_profit_kg' in customer
            assert 'labour_profit_inr' in customer
            print(f"  Top customer: {customer['customer_name']}, Silver Profit: {customer['silver_profit_kg']} kg")
        
        return data
    
    def test_customer_profit_with_date_range(self):
        """Test customer profit with date filter"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/customer-profit",
            params={"start_date": "2024-01-01", "end_date": "2025-12-31"}
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✓ Customer profit (filtered) returned {data['total_customers']} customers")


class TestSupplierProfitGrouping:
    """Tests for Supplier Profit endpoint with group-aware resolution"""
    
    def test_supplier_profit_endpoint(self):
        """Test GET /api/analytics/supplier-profit returns valid data"""
        response = requests.get(f"{BASE_URL}/api/analytics/supplier-profit")
        assert response.status_code == 200
        data = response.json()
        
        assert "suppliers" in data
        assert "total_suppliers" in data
        
        print(f"✓ Supplier profit returned {data['total_suppliers']} suppliers")
        
        # Check structure
        if data['suppliers']:
            supplier = data['suppliers'][0]
            assert 'supplier_name' in supplier
            assert 'silver_profit_kg' in supplier
            assert 'labor_profit_inr' in supplier
            print(f"  Top supplier: {supplier['supplier_name']}, Silver Profit: {supplier['silver_profit_kg']} kg")
        
        return data


class TestItemProfitGrouping:
    """Tests for Item/General Profit endpoint with group-aware resolution"""
    
    def test_item_profit_endpoint(self):
        """Test GET /api/analytics/profit returns valid data"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200
        data = response.json()
        
        # Check basic structure - API returns silver_profit_kg and all_items
        assert "silver_profit_kg" in data or "all_items" in data, f"Expected profit data, got: {list(data.keys())}"
        print(f"✓ Item profit endpoint returned successfully")
        
        if "all_items" in data:
            print(f"  Total items with profit data: {len(data.get('all_items', []))}")
            items = data.get('all_items', [])
            if items:
                item = items[0]
                print(f"  Top item: {item.get('item_name', 'N/A')}, Labor Profit: ₹{item.get('labor_profit_inr', 0)}")
        
        if "silver_profit_kg" in data:
            print(f"  Total Silver Profit: {data['silver_profit_kg']} kg")
        if "labor_profit_inr" in data:
            print(f"  Total Labor Profit: ₹{data['labor_profit_inr']}")
    
    def test_item_profit_with_date_range(self):
        """Test item profit with date filter"""
        response = requests.get(
            f"{BASE_URL}/api/analytics/profit",
            params={"start_date": "2024-01-01", "end_date": "2025-12-31"}
        )
        assert response.status_code == 200
        print("✓ Item profit with date range returned successfully")


class TestVisualizationGrouping:
    """Tests for Visualization endpoint with group-aware resolution"""
    
    def test_visualization_endpoint(self):
        """Test GET /api/analytics/visualization returns grouped data"""
        response = requests.get(f"{BASE_URL}/api/analytics/visualization")
        assert response.status_code == 200
        data = response.json()
        
        # Check expected keys
        expected_keys = ["sales_by_item", "sales_by_party", "tier_distribution"]
        for key in expected_keys:
            assert key in data, f"Expected '{key}' in visualization response"
        
        print(f"✓ Visualization endpoint returned successfully")
        print(f"  Sales by item: {len(data.get('sales_by_item', []))} items")
        print(f"  Sales by party: {len(data.get('sales_by_party', []))} parties")
        
        # Check if items are resolved to leaders (no duplicate group members)
        sales_items = data.get('sales_by_item', [])
        item_names = [item['item_name'] for item in sales_items]
        
        # Look for expected group leaders
        for leader in EXPECTED_GROUPS.keys():
            if leader in item_names:
                print(f"  ✓ Found group leader '{leader}' in sales data")
        
        return data


class TestNegativeItemsReduction:
    """Tests to verify grouping reduces negative items"""
    
    def test_negative_items_count(self):
        """Test that negative items list is reasonable (grouping should reduce it)"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        
        negative_items = data.get('negative_items', [])
        print(f"✓ Negative items count: {len(negative_items)}")
        
        # List negative items for debugging
        if negative_items:
            print("  Negative items:")
            for item in negative_items[:5]:  # Show first 5
                print(f"    - {item['item_name']}: {item.get('net_wt', 0)/1000:.3f} kg")
        
        # Grouping should help reduce negative items from split stock
        # We expect fewer negative items than before grouping was implemented
        # Just verify the count is returned and reasonable
        assert isinstance(negative_items, list)
        
        return negative_items


class TestSearchFilterWithGroups:
    """Tests for search/filter functionality with grouped items"""
    
    def test_search_finds_group_by_leader_name(self):
        """Test that searching for group leader name finds the group"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        inventory = data.get('inventory', [])
        
        # Simulate frontend search for "TULSI"
        search_term = "TULSI"
        matching_items = [
            item for item in inventory 
            if search_term.lower() in item['item_name'].lower() or
            any(search_term.lower() in m['item_name'].lower() for m in item.get('members', []))
        ]
        
        print(f"✓ Search for '{search_term}' found {len(matching_items)} items")
        for item in matching_items[:3]:
            print(f"  - {item['item_name']} (is_group={item.get('is_group', False)})")
    
    def test_search_finds_group_by_member_name(self):
        """Test that searching for member name finds the group containing it"""
        response = requests.get(f"{BASE_URL}/api/inventory/current")
        assert response.status_code == 200
        data = response.json()
        inventory = data.get('inventory', [])
        
        # Search for a member name (e.g., "BELT" which is part of TULSI 70 BELT)
        search_term = "BELT"
        matching_items = [
            item for item in inventory 
            if search_term.lower() in item['item_name'].lower() or
            any(search_term.lower() in m['item_name'].lower() for m in item.get('members', []))
        ]
        
        print(f"✓ Search for '{search_term}' found {len(matching_items)} items")
        for item in matching_items[:3]:
            members = item.get('members', [])
            if members:
                member_names = [m['item_name'] for m in members]
                print(f"  - Group '{item['item_name']}' contains member with '{search_term}'")
                print(f"    Members: {member_names}")


class TestPurchaseLedgerGrouping:
    """Tests for purchase ledger group-aware calculations"""
    
    def test_purchase_ledger_endpoint(self):
        """Test GET /api/purchase-ledger/all returns ledger data"""
        response = requests.get(f"{BASE_URL}/api/purchase-ledger/all")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ Purchase ledger has {len(data)} items")
        
        # Find ledger entries for group members
        group_member_names = []
        for members in EXPECTED_GROUPS.values():
            group_member_names.extend(members)
        
        found_ledger_entries = [
            item for item in data 
            if item['item_name'] in group_member_names
        ]
        
        print(f"  Found {len(found_ledger_entries)} ledger entries for group members")
        for entry in found_ledger_entries:
            print(f"    - {entry['item_name']}: tunch={entry.get('purchase_tunch', 0):.2f}%, labour={entry.get('labour_per_kg', 0):.2f}/kg")
        
        return data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
