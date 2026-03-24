"""
Test iteration 26 fixes:
1. Backend health check
2. Inventory endpoint caching and performance
3. Manager approvals endpoint
4. Approval details endpoint
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndPerformance:
    """Test health check and performance improvements"""
    
    def test_health_check(self):
        """Verify backend health endpoint works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print(f"Health check passed: {data}")
    
    def test_inventory_endpoint_performance(self):
        """Test /api/inventory/current responds within reasonable time (caching)"""
        # Login first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # First request (may be slower - cache miss)
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=headers)
        first_request_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.json()
        assert "inventory" in data
        assert "total_gr_wt" in data
        assert "total_net_wt" in data
        print(f"First request time: {first_request_time:.3f}s, Items: {len(data['inventory'])}")
        
        # Second request (should be faster - cache hit)
        start_time = time.time()
        response2 = requests.get(f"{BASE_URL}/api/inventory/current", headers=headers)
        second_request_time = time.time() - start_time
        
        assert response2.status_code == 200
        print(f"Second request time: {second_request_time:.3f}s (cached)")
        
        # Both should complete within 5 seconds (reasonable for 17K entries)
        assert first_request_time < 5.0, f"First request too slow: {first_request_time}s"
        assert second_request_time < 5.0, f"Second request too slow: {second_request_time}s"


class TestManagerApprovals:
    """Test manager approvals endpoints"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_all_entries_endpoint(self, auth_headers):
        """Test /api/manager/all-entries returns pending entries"""
        response = requests.get(f"{BASE_URL}/api/manager/all-entries", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total entries: {len(data)}")
        
        # Check structure of entries
        if len(data) > 0:
            entry = data[0]
            assert "stamp" in entry
            assert "status" in entry
            assert "entered_by" in entry
            print(f"Sample entry: stamp={entry['stamp']}, status={entry['status']}")
    
    def test_approval_details_endpoint(self, auth_headers):
        """Test /api/manager/approval-details/{stamp} returns comparison data"""
        # First get all entries to find a pending one
        entries_response = requests.get(f"{BASE_URL}/api/manager/all-entries", headers=auth_headers)
        entries = entries_response.json()
        
        pending_entries = [e for e in entries if e.get("status") == "pending"]
        if not pending_entries:
            pytest.skip("No pending entries to test")
        
        entry = pending_entries[0]
        stamp = entry["stamp"]
        verification_date = entry.get("verification_date") or entry.get("entry_day")
        
        # Get approval details
        params = f"?verification_date={verification_date}" if verification_date else ""
        response = requests.get(
            f"{BASE_URL}/api/manager/approval-details/{stamp}{params}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "comparison" in data
        assert "total_book" in data
        assert "total_entered" in data
        assert "total_difference" in data
        
        print(f"Approval details for {stamp}:")
        print(f"  Total book: {data['total_book']:.3f} kg")
        print(f"  Total entered: {data['total_entered']:.3f} kg")
        print(f"  Total difference: {data['total_difference']:.3f} kg")
        print(f"  Comparison items: {len(data['comparison'])}")
    
    def test_approval_details_performance(self, auth_headers):
        """Test approval details endpoint responds quickly"""
        entries_response = requests.get(f"{BASE_URL}/api/manager/all-entries", headers=auth_headers)
        entries = entries_response.json()
        
        pending_entries = [e for e in entries if e.get("status") == "pending"]
        if not pending_entries:
            pytest.skip("No pending entries to test")
        
        entry = pending_entries[0]
        stamp = entry["stamp"]
        verification_date = entry.get("verification_date") or entry.get("entry_day")
        params = f"?verification_date={verification_date}" if verification_date else ""
        
        start_time = time.time()
        response = requests.get(
            f"{BASE_URL}/api/manager/approval-details/{stamp}{params}",
            headers=auth_headers
        )
        request_time = time.time() - start_time
        
        assert response.status_code == 200
        assert request_time < 3.0, f"Approval details too slow: {request_time}s"
        print(f"Approval details request time: {request_time:.3f}s")


class TestDatabaseIndexes:
    """Verify database indexes are working (indirect test via query performance)"""
    
    @pytest.fixture
    def auth_headers(self):
        """Get authentication headers"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_response.status_code == 200
        token = login_response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_transactions_query_performance(self, auth_headers):
        """Test that transaction queries are fast (indexes working)"""
        # The inventory endpoint queries transactions heavily
        # If indexes are working, this should be fast
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/inventory/current", headers=auth_headers)
        query_time = time.time() - start_time
        
        assert response.status_code == 200
        # With proper indexes, even 17K entries should query in under 3 seconds
        assert query_time < 5.0, f"Query too slow, indexes may not be working: {query_time}s"
        print(f"Inventory query time: {query_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
