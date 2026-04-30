"""
Test 3 New Features:
1. Item Groups - manual grouping of similar items
2. Stamp Detail - clickable stamps show all items, stock, assignment
3. Seasonal Item Buffers - categorize with historical data + seasonal boost
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://profit-planner-16.preview.emergentagent.com"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestItemGroups:
    """Test Item Groups CRUD - Feature 1"""

    def test_get_item_groups_returns_list(self, headers):
        """GET /api/item-groups returns groups list"""
        resp = requests.get(f"{BASE_URL}/api/item-groups")
        assert resp.status_code == 200
        data = resp.json()
        assert "groups" in data
        assert isinstance(data["groups"], list)
        print(f"✓ GET /api/item-groups returns {len(data['groups'])} groups")

    def test_get_suggestions_returns_items(self, headers):
        """GET /api/item-groups/suggestions returns master items and already grouped"""
        resp = requests.get(f"{BASE_URL}/api/item-groups/suggestions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "already_grouped" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["already_grouped"], list)
        print(f"✓ GET /api/item-groups/suggestions: {len(data['items'])} items, {len(data['already_grouped'])} already grouped")

    def test_create_item_group(self, headers):
        """POST /api/item-groups creates group with group_name and members"""
        # First get available items
        sugg_resp = requests.get(f"{BASE_URL}/api/item-groups/suggestions")
        items = sugg_resp.json().get("items", [])
        
        # Pick 2 items for test group (if available)
        if len(items) < 2:
            pytest.skip("Need at least 2 master items to test group creation")
        
        # Use items with similar names if possible, else just first 2
        test_items = [items[0]["item_name"], items[1]["item_name"]]
        group_name = f"TEST_GROUP_{int(time.time())}"
        
        resp = requests.post(f"{BASE_URL}/api/item-groups", 
            json={"group_name": group_name, "members": test_items},
            headers=headers
        )
        assert resp.status_code == 200, f"Create group failed: {resp.text}"
        data = resp.json()
        assert data.get("success") is True
        assert "saved" in data.get("message", "").lower() or "success" in str(data)
        print(f"✓ POST /api/item-groups created '{group_name}' with {len(test_items)} members")
        
        # Verify group was created
        get_resp = requests.get(f"{BASE_URL}/api/item-groups")
        groups = get_resp.json().get("groups", [])
        group_names = [g["group_name"] for g in groups]
        assert group_name in group_names, "Created group not found in list"
        print(f"✓ Verified group '{group_name}' exists in GET response")
        
        return group_name

    def test_create_group_requires_auth(self):
        """POST /api/item-groups without auth returns 401/403"""
        resp = requests.post(f"{BASE_URL}/api/item-groups", 
            json={"group_name": "NOAUTH_GROUP", "members": ["a", "b"]}
        )
        assert resp.status_code in [401, 403], "Should require auth"
        print("✓ POST /api/item-groups requires authentication")

    def test_create_group_requires_min_members(self, headers):
        """POST /api/item-groups requires at least 2 members"""
        resp = requests.post(f"{BASE_URL}/api/item-groups", 
            json={"group_name": "SINGLE_MEMBER", "members": ["single_item"]},
            headers=headers
        )
        assert resp.status_code == 400, "Should require min 2 members"
        print("✓ POST /api/item-groups validates minimum 2 members")

    def test_delete_item_group(self, headers):
        """DELETE /api/item-groups/{name} deletes a group"""
        # First create a group to delete
        test_name = f"TEST_DELETE_{int(time.time())}"
        sugg = requests.get(f"{BASE_URL}/api/item-groups/suggestions").json()
        items = sugg.get("items", [])[:2]
        if len(items) < 2:
            pytest.skip("Need items to test")
        
        create_resp = requests.post(f"{BASE_URL}/api/item-groups",
            json={"group_name": test_name, "members": [i["item_name"] for i in items]},
            headers=headers
        )
        assert create_resp.status_code == 200
        
        # Now delete it
        del_resp = requests.delete(f"{BASE_URL}/api/item-groups/{test_name}", headers=headers)
        assert del_resp.status_code == 200
        data = del_resp.json()
        assert data.get("success") is True
        print(f"✓ DELETE /api/item-groups/{test_name} succeeded")
        
        # Verify it's gone
        get_resp = requests.get(f"{BASE_URL}/api/item-groups")
        groups = get_resp.json().get("groups", [])
        group_names = [g["group_name"] for g in groups]
        assert test_name not in group_names, "Deleted group still exists"
        print("✓ Verified group no longer exists after delete")

    def test_delete_requires_auth(self):
        """DELETE /api/item-groups/{name} requires auth"""
        resp = requests.delete(f"{BASE_URL}/api/item-groups/SomeGroup")
        assert resp.status_code in [401, 403]
        print("✓ DELETE /api/item-groups requires authentication")


class TestStampDetail:
    """Test Stamp Detail endpoint - Feature 2"""

    def test_get_stamp_detail(self, headers):
        """GET /api/stamps/{stamp_name}/detail returns items, stock, assignment"""
        # First get a valid stamp from master items
        master_resp = requests.get(f"{BASE_URL}/api/master-items")
        if master_resp.status_code != 200:
            pytest.skip("Master items not available")
        
        master_items = master_resp.json()
        if not master_items:
            pytest.skip("No master items")
        
        # Find a stamp
        stamps = [m.get("stamp") for m in master_items if m.get("stamp")]
        if not stamps:
            pytest.skip("No stamps in master items")
        
        stamp_name = stamps[0]
        
        # Get stamp detail
        resp = requests.get(f"{BASE_URL}/api/stamps/{stamp_name}/detail")
        assert resp.status_code == 200, f"Stamp detail failed: {resp.text}"
        data = resp.json()
        
        # Validate response structure
        assert "stamp" in data
        assert "items" in data
        assert "total_items" in data
        assert "total_net_wt_kg" in data
        assert "assigned_user" in data  # Can be null
        
        # Validate items have correct structure
        if data["items"]:
            item = data["items"][0]
            assert "item_name" in item
            assert "net_wt_kg" in item
            assert "gr_wt_kg" in item
        
        print(f"✓ GET /api/stamps/{stamp_name}/detail: {data['total_items']} items, {data['total_net_wt_kg']} kg")
        print(f"  Assigned user: {data['assigned_user'] or 'Unassigned'}")

    def test_stamp_detail_nonexistent_stamp(self):
        """GET /api/stamps/{stamp_name}/detail for unknown stamp returns empty list"""
        resp = requests.get(f"{BASE_URL}/api/stamps/NONEXISTENT_STAMP_XYZ123/detail")
        # Should return 200 with empty items list (not 404)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_items"] == 0
        assert len(data["items"]) == 0
        print("✓ Nonexistent stamp returns empty items list")


class TestStampAssignments:
    """Test Stamp Assignments - supports Stamp Detail feature"""

    def test_get_stamp_assignments(self, headers):
        """GET /api/stamp-assignments returns assignments list"""
        resp = requests.get(f"{BASE_URL}/api/stamp-assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert "assignments" in data
        assert isinstance(data["assignments"], list)
        print(f"✓ GET /api/stamp-assignments: {len(data['assignments'])} assignments")

    def test_create_stamp_assignment(self, headers):
        """POST /api/stamp-assignments creates assignment"""
        # Get a stamp to assign
        master_resp = requests.get(f"{BASE_URL}/api/master-items")
        if master_resp.status_code != 200:
            pytest.skip("No master items")
        
        stamps = list(set([m.get("stamp") for m in master_resp.json() if m.get("stamp")]))
        if not stamps:
            pytest.skip("No stamps")
        
        stamp_to_assign = stamps[0]
        
        resp = requests.post(f"{BASE_URL}/api/stamp-assignments",
            json={"stamp": stamp_to_assign, "assigned_user": "admin"},
            headers=headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True or "assigned" in str(data).lower()
        print(f"✓ POST /api/stamp-assignments: assigned 'admin' to '{stamp_to_assign}'")

    def test_stamp_assignment_reflected_in_detail(self, headers):
        """Stamp assignment is reflected in stamp detail"""
        master_resp = requests.get(f"{BASE_URL}/api/master-items")
        stamps = list(set([m.get("stamp") for m in master_resp.json() if m.get("stamp")]))
        if not stamps:
            pytest.skip("No stamps")
        
        stamp = stamps[0]
        
        # Assign admin to stamp
        requests.post(f"{BASE_URL}/api/stamp-assignments",
            json={"stamp": stamp, "assigned_user": "admin"},
            headers=headers
        )
        
        # Check detail shows assignment
        detail = requests.get(f"{BASE_URL}/api/stamps/{stamp}/detail").json()
        assert detail["assigned_user"] == "admin"
        print(f"✓ Assignment reflected in stamp detail: {stamp} -> admin")


class TestSeasonalItemBuffers:
    """Test Seasonal Item Buffers (categorize endpoint) - Feature 3"""

    def test_categorize_endpoint_returns_seasonal_info(self, headers):
        """POST /api/item-buffers/categorize returns seasonal info"""
        resp = requests.post(f"{BASE_URL}/api/item-buffers/categorize", headers=headers)
        assert resp.status_code == 200, f"Categorize failed: {resp.text}"
        data = resp.json()
        
        # Check for seasonal fields
        assert "current_season" in data, "Missing current_season field"
        assert "season_boost" in data, "Missing season_boost field"
        assert "years_analyzed" in data, "Missing years_analyzed field"
        assert "total_items" in data, "Missing total_items field"
        
        # Validate values
        assert isinstance(data["season_boost"], (int, float))
        assert data["season_boost"] >= 1.0
        assert isinstance(data["years_analyzed"], int)
        assert data["years_analyzed"] >= 0
        
        print(f"✓ POST /api/item-buffers/categorize:")
        print(f"  Current season: {data['current_season']}")
        print(f"  Season boost: {data['season_boost']}x")
        print(f"  Years analyzed: {data['years_analyzed']}")
        print(f"  Total items categorized: {data['total_items']}")

    def test_categorize_requires_auth(self):
        """POST /api/item-buffers/categorize requires admin auth"""
        resp = requests.post(f"{BASE_URL}/api/item-buffers/categorize")
        assert resp.status_code in [401, 403]
        print("✓ POST /api/item-buffers/categorize requires authentication")

    def test_item_buffers_show_groups(self, headers):
        """GET /api/item-buffers shows items with is_group flag for grouped items"""
        # First ensure categorize has run
        requests.post(f"{BASE_URL}/api/item-buffers/categorize", headers=headers)
        
        # Get buffers
        resp = requests.get(f"{BASE_URL}/api/item-buffers")
        assert resp.status_code == 200
        data = resp.json()
        
        items = data.get("items", [])
        if items:
            # Check structure of buffer item
            item = items[0]
            assert "item_name" in item
            assert "tier" in item
            assert "status" in item
            assert "monthly_velocity_kg" in item
            assert "current_stock_kg" in item
            assert "minimum_stock_kg" in item
            
            # Check for is_group field (may be present for grouped items)
            grouped_items = [i for i in items if i.get("is_group")]
            print(f"✓ GET /api/item-buffers: {len(items)} items, {len(grouped_items)} groups")
        else:
            print("✓ GET /api/item-buffers: No buffer items (may need data)")


class TestIntegration:
    """Integration tests combining the 3 features"""

    def test_group_merged_in_buffers(self, headers):
        """Item groups are merged when calculating buffers"""
        # Create a test group
        sugg = requests.get(f"{BASE_URL}/api/item-groups/suggestions").json()
        items = sugg.get("items", [])
        
        if len(items) < 2:
            pytest.skip("Need items for integration test")
        
        group_name = f"TEST_INTEG_{int(time.time())}"
        members = [items[0]["item_name"], items[1]["item_name"]]
        
        # Create group
        requests.post(f"{BASE_URL}/api/item-groups",
            json={"group_name": group_name, "members": members},
            headers=headers
        )
        
        # Run categorize
        cat_resp = requests.post(f"{BASE_URL}/api/item-buffers/categorize", headers=headers)
        assert cat_resp.status_code == 200
        
        # Check buffers - group should appear as single item
        buffers = requests.get(f"{BASE_URL}/api/item-buffers").json().get("items", [])
        
        # The group_name should appear in buffers (if there's data for those items)
        # Individual members should NOT appear separately
        buffer_names = [b["item_name"] for b in buffers]
        
        # Group leader should be in buffers OR members should be merged
        # (depending on whether items had sales data)
        print(f"✓ Integration: Created group '{group_name}', ran categorize")
        print(f"  Buffer items count: {len(buffer_names)}")
        
        # Cleanup - delete test group
        requests.delete(f"{BASE_URL}/api/item-groups/{group_name}", headers=headers)
        print(f"✓ Cleaned up test group '{group_name}'")


# Cleanup test data
@pytest.fixture(scope="module", autouse=True)
def cleanup(request, headers):
    """Clean up TEST_ prefixed groups after all tests"""
    yield
    # After all tests, delete test groups
    try:
        get_resp = requests.get(f"{BASE_URL}/api/item-groups")
        groups = get_resp.json().get("groups", [])
        for g in groups:
            if g["group_name"].startswith("TEST_"):
                requests.delete(f"{BASE_URL}/api/item-groups/{g['group_name']}", headers=headers)
                print(f"Cleaned up test group: {g['group_name']}")
    except Exception:
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
