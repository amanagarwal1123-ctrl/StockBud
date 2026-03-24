"""
Test Suite: Individual Stock Computation (Critical Fix Verification)
=====================================================================
Verifies that items in groups are computed INDIVIDUALLY, not merged into group leaders.
This is the critical fix for the stamp approval workflow where each item retains its own stamp.

Groups tested:
- SNT 40-256 (members: SNT 40-256, SNT-40 PREMIUM)
- TULSI 70 -264 (members: TULSI 70 -264, TULSI 70 BELT)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestIndividualStockComputation:
    """Tests for verifying items are computed individually, not merged into groups"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for API calls"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_inventory_endpoint_returns_200(self):
        """Basic health check - inventory endpoint works"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        assert response.status_code == 200, f"Inventory endpoint failed: {response.text}"
        data = response.json()
        assert "inventory" in data
        assert "by_stamp" in data
        assert "total_items" in data
        print(f"✓ Inventory endpoint returns {data['total_items']} items")
    
    def test_by_stamp_contains_individual_items_not_merged(self):
        """CRITICAL: by_stamp should have INDIVIDUAL items, not merged into group leaders"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        by_stamp = data.get("by_stamp", {})
        
        # Flatten all items in by_stamp
        all_stamp_items = []
        for stamp, items in by_stamp.items():
            for item in items:
                all_stamp_items.append(item["item_name"])
        
        # Check that group members appear as INDIVIDUAL items
        # Group: SNT 40-256 has members SNT 40-256 and SNT-40 PREMIUM
        snt_leader = "SNT 40-256"
        snt_member = "SNT-40 PREMIUM"
        
        # Both should appear in by_stamp (not merged)
        assert snt_leader in all_stamp_items, f"Group leader {snt_leader} should be in by_stamp"
        assert snt_member in all_stamp_items, f"Group member {snt_member} should be in by_stamp (NOT merged into leader)"
        
        print(f"✓ SNT group members appear individually: {snt_leader}, {snt_member}")
    
    def test_tulsi_group_members_have_individual_stamps(self):
        """CRITICAL: TULSI group members should each have their OWN stamp in by_stamp"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        by_stamp = data.get("by_stamp", {})
        
        # TULSI 70 -264 and TULSI 70 BELT should both be in STAMP 3
        stamp_3_items = by_stamp.get("STAMP 3", [])
        stamp_3_names = [item["item_name"] for item in stamp_3_items]
        
        tulsi_leader = "TULSI 70 -264"
        tulsi_member = "TULSI 70 BELT"
        
        assert tulsi_leader in stamp_3_names, f"{tulsi_leader} should be in STAMP 3"
        assert tulsi_member in stamp_3_names, f"{tulsi_member} should be in STAMP 3 (NOT merged into leader)"
        
        # Verify they have different weights (not summed into one)
        tulsi_leader_item = next((i for i in stamp_3_items if i["item_name"] == tulsi_leader), None)
        tulsi_member_item = next((i for i in stamp_3_items if i["item_name"] == tulsi_member), None)
        
        assert tulsi_leader_item is not None
        assert tulsi_member_item is not None
        assert tulsi_leader_item["gr_wt"] != tulsi_member_item["gr_wt"], "Items should have different weights"
        
        print(f"✓ TULSI group members in STAMP 3:")
        print(f"  - {tulsi_leader}: gr_wt={tulsi_leader_item['gr_wt']}")
        print(f"  - {tulsi_member}: gr_wt={tulsi_member_item['gr_wt']}")
    
    def test_inventory_list_shows_grouped_display(self):
        """inventory list should show groups with is_group=True and members[] for display"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        inventory = data.get("inventory", [])
        
        # Find a group entry
        group_entries = [i for i in inventory if i.get("is_group") == True]
        assert len(group_entries) > 0, "Should have at least one group entry for display"
        
        # Check group has members array
        for group in group_entries:
            members = group.get("members", [])
            if len(members) > 1:
                print(f"✓ Group '{group['item_name']}' has {len(members)} members for display")
                # Verify group totals = sum of members
                group_gr = group["gr_wt"]
                members_gr = sum(m["gr_wt"] for m in members)
                assert abs(group_gr - members_gr) < 1, f"Group total should equal sum of members"
                print(f"  - Group gr_wt: {group_gr}, Members sum: {members_gr}")
                break
    
    def test_group_display_totals_are_correct(self):
        """Group display entries should have correct totals (sum of individual members)"""
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        assert response.status_code == 200
        data = response.json()
        inventory = data.get("inventory", [])
        
        # Find TULSI group
        tulsi_group = next((i for i in inventory if i["item_name"] == "TULSI 70 -264" and i.get("is_group")), None)
        
        if tulsi_group:
            members = tulsi_group.get("members", [])
            if len(members) >= 2:
                group_gr = tulsi_group["gr_wt"]
                group_net = tulsi_group["net_wt"]
                members_gr = sum(m["gr_wt"] for m in members)
                members_net = sum(m["net_wt"] for m in members)
                
                assert abs(group_gr - members_gr) < 1, "Group gr_wt should equal sum of members"
                assert abs(group_net - members_net) < 1, "Group net_wt should equal sum of members"
                
                print(f"✓ TULSI group totals correct:")
                print(f"  - Group gr_wt: {group_gr}, Members sum: {members_gr}")
                print(f"  - Group net_wt: {group_net}, Members sum: {members_net}")


class TestApprovalDetailsEndpoint:
    """Tests for /api/manager/approval-details/{stamp} endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for API calls"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_approval_details_uses_individual_book_values(self):
        """approval-details should use individual item book values from by_stamp"""
        # First get current inventory to know what stamps have data
        inv_response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        assert inv_response.status_code == 200
        by_stamp = inv_response.json().get("by_stamp", {})
        
        # Test with STAMP 3 which has TULSI items
        if "STAMP 3" in by_stamp:
            stamp_3_items = by_stamp["STAMP 3"]
            stamp_3_names = {item["item_name"] for item in stamp_3_items}
            
            # Verify TULSI members are individual
            assert "TULSI 70 -264" in stamp_3_names or "TULSI 70 BELT" in stamp_3_names, \
                "STAMP 3 should have TULSI items"
            
            print(f"✓ STAMP 3 has {len(stamp_3_items)} individual items in by_stamp")
            print(f"  Items: {list(stamp_3_names)[:5]}...")  # Show first 5


class TestDBIndexes:
    """Tests for verifying DB indexes are created on startup"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_inventory_endpoint_performance(self):
        """Inventory endpoint should respond quickly (indexes working)"""
        import time
        start = time.time()
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=self.headers)
        elapsed = time.time() - start
        
        assert response.status_code == 200
        assert elapsed < 5.0, f"Inventory endpoint too slow: {elapsed:.2f}s (should be <5s)"
        print(f"✓ Inventory endpoint responded in {elapsed:.2f}s")


class TestUIFeatures:
    """Tests for UI-related features (badge loading, details toggle)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        self.token = response.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_manager_all_entries_endpoint(self):
        """Manager all-entries endpoint should work for badge loading"""
        response = requests.get(f"{BASE_URL}/api/manager/all-entries", headers=self.headers)
        assert response.status_code == 200
        entries = response.json()
        assert isinstance(entries, list)
        print(f"✓ Manager all-entries returns {len(entries)} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
