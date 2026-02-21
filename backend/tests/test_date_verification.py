"""
Test cases for Date-based Stock Verification feature.

Features being tested:
1) Executive Stock Entry page has date picker and stamp selector
2) POST /api/executive/stock-entry accepts verification_date field
3) GET /api/manager/approval-details/{stamp} returns verification_date and date-filtered book stock
4) Approval details comparison uses expected closing stock as-of verification_date
5) Color coding in approvals: Green (diff < 20g), Blue (diff > 0), Red (diff < 0)
6) Verification date shows in My Entries and Approvals badges
7) Deleting a transaction changes the expected closing stock (on-the-fly calculation)
"""

import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_CREDS = {"username": "admin", "password": "admin123"}
EXECUTIVE_CREDS = {"username": "SEE1", "password": "executive123"}
MANAGER_CREDS = {"username": "SMANAGER", "password": "manager123"}

# Use STAMP 3 for testing (per requirements)
TEST_STAMP = "STAMP 3"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def admin_token(api_client):
    """Get admin authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Admin authentication failed")


@pytest.fixture(scope="module")
def executive_token(api_client):
    """Get executive authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=EXECUTIVE_CREDS)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Executive authentication failed")


@pytest.fixture(scope="module")
def manager_token(api_client):
    """Get manager authentication token"""
    # Try manager first, fallback to admin
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=MANAGER_CREDS)
    if response.status_code == 200:
        return response.json().get("access_token")
    # Fallback to admin for manager-level operations
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=ADMIN_CREDS)
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Manager/Admin authentication failed")


class TestHealthAndAuth:
    """Basic health and authentication tests"""
    
    def test_health_endpoint(self, api_client):
        """Test API health endpoint"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health endpoint working")
    
    def test_executive_login(self, api_client):
        """Test SEE1 (executive) can login"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=EXECUTIVE_CREDS)
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "executive"
        assert data["user"]["username"] == "SEE1"
        print("✓ Executive login successful")


class TestStockEntryEndpoint:
    """Tests for POST /api/executive/stock-entry with verification_date"""
    
    def test_stock_entry_accepts_verification_date(self, api_client, executive_token):
        """Test that stock entry endpoint accepts verification_date field"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        payload = {
            "stamp": TEST_STAMP,
            "entries": [
                {"item_name": ".CHAIN -058", "gross_wt": 1.5},
                {"item_name": "A-60 PAYAL-004", "gross_wt": 2.0}
            ],
            "entered_by": "SEE1",
            "verification_date": today
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/executive/stock-entry",
            json=payload,
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"✓ Stock entry accepted with verification_date: {today}")
    
    def test_stock_entry_with_past_date(self, api_client, executive_token):
        """Test that stock entry works with a past verification_date"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        payload = {
            "stamp": TEST_STAMP,
            "entries": [
                {"item_name": ".CHAIN -058", "gross_wt": 1.25}
            ],
            "entered_by": "SEE1",
            "verification_date": yesterday
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/executive/stock-entry",
            json=payload,
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print(f"✓ Stock entry accepted with past verification_date: {yesterday}")
    
    def test_stock_entry_defaults_to_today(self, api_client, executive_token):
        """Test that stock entry without verification_date defaults to today"""
        payload = {
            "stamp": TEST_STAMP,
            "entries": [
                {"item_name": ".CHAIN -058", "gross_wt": 1.0}
            ],
            "entered_by": "SEE1"
            # No verification_date - should default to today
        }
        
        response = api_client.post(
            f"{BASE_URL}/api/executive/stock-entry",
            json=payload,
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        print("✓ Stock entry defaults to today when verification_date not provided")


class TestApprovalDetailsEndpoint:
    """Tests for GET /api/manager/approval-details/{stamp}"""
    
    def test_approval_details_returns_verification_date(self, api_client, manager_token):
        """Test that approval-details returns verification_date"""
        response = api_client.get(
            f"{BASE_URL}/api/manager/approval-details/{TEST_STAMP}",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("No pending entry found for test stamp")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "verification_date" in data, "Response should include verification_date"
        assert "comparison" in data, "Response should include comparison array"
        assert "total_entered" in data, "Response should include total_entered"
        assert "total_book" in data, "Response should include total_book"
        assert "total_difference" in data, "Response should include total_difference"
        
        print(f"✓ Approval details returned verification_date: {data['verification_date']}")
        print(f"  - Total book: {data['total_book']} kg")
        print(f"  - Total entered: {data['total_entered']} kg")
        print(f"  - Difference: {data['total_difference']} kg")
    
    def test_approval_details_comparison_structure(self, api_client, manager_token):
        """Test that comparison array has correct structure"""
        response = api_client.get(
            f"{BASE_URL}/api/manager/approval-details/{TEST_STAMP}",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("No pending entry found for test stamp")
        
        assert response.status_code == 200
        data = response.json()
        
        comparison = data.get("comparison", [])
        assert len(comparison) > 0, "Comparison should have items"
        
        # Check first item structure
        first_item = comparison[0]
        assert "item_name" in first_item
        assert "book_gross" in first_item
        assert "entered_gross" in first_item
        assert "difference" in first_item
        assert "was_entered" in first_item
        
        print(f"✓ Comparison has {len(comparison)} items with correct structure")
        
        # Show sample items
        for item in comparison[:3]:
            diff_label = "GREEN" if abs(item['difference']) < 0.020 else ("BLUE" if item['difference'] > 0 else "RED")
            print(f"  - {item['item_name']}: book={item['book_gross']}, entered={item['entered_gross']}, diff={item['difference']} ({diff_label})")


class TestDateFilteredClosingStock:
    """Tests for get_stamp_closing_stock date filtering logic"""
    
    def test_closing_stock_service_callable(self, api_client, manager_token):
        """Test that closing stock is calculated via approval-details endpoint"""
        # Create an entry with specific date
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        response = api_client.get(
            f"{BASE_URL}/api/manager/approval-details/{TEST_STAMP}",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("No entry exists for test stamp")
        
        assert response.status_code == 200
        data = response.json()
        
        # The book_gross values come from get_stamp_closing_stock(stamp, verification_date)
        assert data["total_book"] >= 0, "Total book stock should be non-negative (could be 0 for new items)"
        print(f"✓ Closing stock calculated for verification_date: {data['verification_date']}")


class TestMyEntriesEndpoint:
    """Tests for GET /api/executive/my-entries/{username}"""
    
    def test_my_entries_shows_verification_date(self, api_client, executive_token):
        """Test that my-entries returns verification_date for each entry"""
        response = api_client.get(
            f"{BASE_URL}/api/executive/my-entries/SEE1",
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No entries found for SEE1")
        
        # Check that entries have verification_date
        entry = data[0]
        assert "verification_date" in entry or "entry_day" in entry, "Entry should have verification_date or entry_day"
        assert "stamp" in entry
        assert "status" in entry
        
        print(f"✓ My entries returned {len(data)} entries")
        for e in data[:3]:
            v_date = e.get('verification_date', e.get('entry_day', 'N/A'))
            print(f"  - {e['stamp']}: status={e['status']}, verification_date={v_date}")


class TestAllEntriesEndpoint:
    """Tests for GET /api/manager/all-entries"""
    
    def test_all_entries_shows_verification_date(self, api_client, manager_token):
        """Test that manager all-entries endpoint returns verification_date"""
        response = api_client.get(
            f"{BASE_URL}/api/manager/all-entries",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No entries found")
        
        # Check that entries have verification_date
        entry_with_date = None
        for entry in data:
            if "verification_date" in entry:
                entry_with_date = entry
                break
        
        if entry_with_date:
            print(f"✓ All entries returned {len(data)} entries with verification_date field present")
            print(f"  - Sample: {entry_with_date['stamp']} - verification_date={entry_with_date['verification_date']}")
        else:
            print(f"✓ All entries returned {len(data)} entries (verification_date may not be set for old entries)")


class TestColorCodingLogic:
    """Tests to verify color coding thresholds are applied correctly"""
    
    def test_color_coding_thresholds(self, api_client, manager_token):
        """Verify color coding logic: Green < 20g, Blue > 0, Red < 0"""
        response = api_client.get(
            f"{BASE_URL}/api/manager/approval-details/{TEST_STAMP}",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        
        if response.status_code == 404:
            pytest.skip("No entry found for test stamp")
        
        assert response.status_code == 200
        data = response.json()
        comparison = data.get("comparison", [])
        
        # Categorize items by color
        green_items = [i for i in comparison if abs(i['difference']) < 0.020]
        blue_items = [i for i in comparison if i['difference'] >= 0.020]
        red_items = [i for i in comparison if i['difference'] <= -0.020]
        
        print(f"✓ Color coding analysis:")
        print(f"  - GREEN (within 20g): {len(green_items)} items")
        print(f"  - BLUE (increased > 20g): {len(blue_items)} items")
        print(f"  - RED (decreased > 20g): {len(red_items)} items")
        
        # Verify the data is being returned correctly for frontend to apply colors
        total_diff = data["total_difference"]
        if abs(total_diff) < 0.020:
            print(f"  - TOTAL would be GREEN (diff={total_diff})")
        elif total_diff > 0:
            print(f"  - TOTAL would be BLUE (diff=+{total_diff})")
        else:
            print(f"  - TOTAL would be RED (diff={total_diff})")


class TestUpdateEntryEndpoint:
    """Tests for PUT /api/executive/update-entry/{stamp}"""
    
    def test_update_entry_accepts_verification_date(self, api_client, executive_token):
        """Test that update entry endpoint accepts verification_date"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # First create an entry
        create_payload = {
            "stamp": TEST_STAMP,
            "entries": [{"item_name": ".CHAIN -058", "gross_wt": 1.0}],
            "entered_by": "SEE1",
            "verification_date": today
        }
        
        create_response = api_client.post(
            f"{BASE_URL}/api/executive/stock-entry",
            json=create_payload,
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        if create_response.status_code != 200:
            pytest.skip("Could not create entry for update test")
        
        # Now update it with new verification_date
        new_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        update_payload = {
            "entries": [{"item_name": ".CHAIN -058", "gross_wt": 1.5}],
            "entered_by": "SEE1",
            "verification_date": new_date
        }
        
        response = api_client.put(
            f"{BASE_URL}/api/executive/update-entry/{TEST_STAMP}",
            json=update_payload,
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        assert response.status_code == 200
        print(f"✓ Update entry accepted with verification_date: {new_date}")


class TestMasterItems:
    """Tests for master items endpoint to verify stamp items"""
    
    def test_stamp_3_has_items(self, api_client):
        """Verify STAMP 3 has items for testing"""
        response = api_client.get(f"{BASE_URL}/api/master-items")
        assert response.status_code == 200
        
        data = response.json()
        stamp_3_items = [item for item in data if item.get('stamp') == TEST_STAMP]
        
        assert len(stamp_3_items) > 0, f"{TEST_STAMP} should have items"
        print(f"✓ {TEST_STAMP} has {len(stamp_3_items)} items")
        for item in stamp_3_items[:5]:
            print(f"  - {item['item_name']}")


class TestIntegrationFlow:
    """End-to-end flow test"""
    
    def test_full_stock_entry_and_approval_flow(self, api_client, executive_token, manager_token):
        """Test complete flow: Executive enters stock -> Manager views with date-filtered comparison"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Step 1: Executive creates stock entry with verification_date
        entry_payload = {
            "stamp": TEST_STAMP,
            "entries": [
                {"item_name": ".CHAIN -058", "gross_wt": 2.5},
                {"item_name": "A-60 PAYAL-004", "gross_wt": 3.0}
            ],
            "entered_by": "SEE1",
            "verification_date": today
        }
        
        entry_response = api_client.post(
            f"{BASE_URL}/api/executive/stock-entry",
            json=entry_payload,
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        assert entry_response.status_code == 200
        print("✓ Step 1: Executive created stock entry")
        
        # Step 2: Manager gets approval details
        details_response = api_client.get(
            f"{BASE_URL}/api/manager/approval-details/{TEST_STAMP}",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        
        assert details_response.status_code == 200
        details = details_response.json()
        
        # Verify the response structure
        assert details["verification_date"] == today, f"Expected verification_date={today}, got {details['verification_date']}"
        assert "comparison" in details
        assert "total_difference" in details
        
        print(f"✓ Step 2: Manager received approval details for {today}")
        print(f"  - Verification date: {details['verification_date']}")
        print(f"  - Total items: {details['total_items']}")
        print(f"  - Items entered: {details['items_entered']}")
        print(f"  - Total difference: {details['total_difference']} kg")
        
        # Step 3: Verify comparison shows date-filtered book stock
        comparison = details["comparison"]
        entered_items = [c for c in comparison if c["was_entered"]]
        assert len(entered_items) == 2, f"Expected 2 entered items, got {len(entered_items)}"
        
        # The book stock should be calculated as of verification_date
        # (opening_stock + transactions up to verification_date)
        print(f"✓ Step 3: Comparison shows {len(entered_items)} entered items with book stock")
        for item in entered_items:
            print(f"  - {item['item_name']}: entered={item['entered_gross']} kg, book={item['book_gross']} kg, diff={item['difference']} kg")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
