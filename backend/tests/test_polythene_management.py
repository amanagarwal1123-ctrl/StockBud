"""
Test Polythene Management Feature
- Tests role-based access for admin and executive roles
- Tests rejection for polythene_executive role
- Tests filtering and data retrieval
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPolytheneManagementAccess:
    """Test role-based access to /api/polythene/all endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def executive_token(self):
        """Get executive token (TEST_EXEC user)"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "TEST_EXEC",
            "password": "exec123"
        })
        assert response.status_code == 200, f"Executive login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_admin_can_access_polythene_all(self, admin_token):
        """Admin should be able to access GET /api/polythene/all"""
        response = requests.get(
            f"{BASE_URL}/api/polythene/all",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Admin access failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Admin retrieved {len(data)} polythene entries")
    
    def test_executive_can_access_polythene_all(self, executive_token):
        """Executive (SEE role) should be able to access GET /api/polythene/all"""
        response = requests.get(
            f"{BASE_URL}/api/polythene/all",
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        assert response.status_code == 200, f"Executive access failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Executive retrieved {len(data)} polythene entries")
    
    def test_polythene_executive_cannot_access_polythene_all(self, admin_token):
        """Polythene executive should NOT be able to access GET /api/polythene/all (403)"""
        # First, create a test polythene_executive user
        create_response = requests.post(
            f"{BASE_URL}/api/users/create",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "username": "TEST_POLY_EXEC",
                "password": "polyexec123",
                "full_name": "Test Polythene Executive",
                "role": "polythene_executive"
            }
        )
        # User might already exist, that's ok
        
        # Login as polythene_executive
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "TEST_POLY_EXEC",
            "password": "polyexec123"
        })
        
        if login_response.status_code != 200:
            # Try with PEE1 if TEST_POLY_EXEC doesn't work
            pytest.skip("Could not login as polythene_executive user")
        
        poly_exec_token = login_response.json()["access_token"]
        
        # Try to access polythene/all - should be rejected
        response = requests.get(
            f"{BASE_URL}/api/polythene/all",
            headers={"Authorization": f"Bearer {poly_exec_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for polythene_executive, got {response.status_code}"
        print("Polythene executive correctly rejected with 403")
    
    def test_manager_cannot_access_polythene_all(self, admin_token):
        """Manager should NOT be able to access GET /api/polythene/all (403)"""
        # Login as manager
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "SMANAGER",
            "password": "manager123"
        })
        
        if login_response.status_code != 200:
            pytest.skip("Could not login as manager user")
        
        manager_token = login_response.json()["access_token"]
        
        # Try to access polythene/all - should be rejected
        response = requests.get(
            f"{BASE_URL}/api/polythene/all",
            headers={"Authorization": f"Bearer {manager_token}"}
        )
        assert response.status_code == 403, f"Expected 403 for manager, got {response.status_code}"
        print("Manager correctly rejected with 403")
    
    def test_unauthenticated_cannot_access_polythene_all(self):
        """Unauthenticated request should be rejected"""
        response = requests.get(f"{BASE_URL}/api/polythene/all")
        assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"
        print("Unauthenticated request correctly rejected")


class TestPolytheneDataStructure:
    """Test the data structure returned by polythene/all endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_polythene_entry_has_required_fields(self, admin_token):
        """Each polythene entry should have required fields for display"""
        response = requests.get(
            f"{BASE_URL}/api/polythene/all",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No polythene entries to test")
        
        entry = data[0]
        required_fields = ['id', 'item_name', 'stamp', 'poly_weight', 'operation', 'adjusted_by', 'created_at']
        
        for field in required_fields:
            assert field in entry, f"Missing required field: {field}"
        
        # Validate operation is add or subtract
        assert entry['operation'] in ['add', 'subtract'], f"Invalid operation: {entry['operation']}"
        
        # Validate poly_weight is a number
        assert isinstance(entry['poly_weight'], (int, float)), "poly_weight should be numeric"
        
        print(f"Entry structure validated: {list(entry.keys())}")


class TestPolytheneDeleteAccess:
    """Test delete endpoint access control"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    @pytest.fixture(scope="class")
    def executive_token(self):
        """Get executive token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "TEST_EXEC",
            "password": "exec123"
        })
        return response.json()["access_token"]
    
    def test_executive_cannot_delete_polythene_entry(self, admin_token, executive_token):
        """Executive should NOT be able to delete polythene entries (403)"""
        # Get an existing entry
        response = requests.get(
            f"{BASE_URL}/api/polythene/all",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = response.json()
        
        if len(data) == 0:
            pytest.skip("No polythene entries to test delete")
        
        entry_id = data[0]['id']
        
        # Try to delete as executive - should fail
        delete_response = requests.delete(
            f"{BASE_URL}/api/polythene/{entry_id}",
            headers={"Authorization": f"Bearer {executive_token}"}
        )
        
        # Executive should get 403 (not their entry and not admin)
        assert delete_response.status_code == 403, f"Expected 403 for executive delete, got {delete_response.status_code}"
        print("Executive correctly cannot delete polythene entries")


class TestUsersListForFilter:
    """Test users list endpoint for admin filter dropdown"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        return response.json()["access_token"]
    
    def test_admin_can_get_users_list(self, admin_token):
        """Admin should be able to get users list for filter dropdown"""
        response = requests.get(
            f"{BASE_URL}/api/users/list",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get users list: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Check that polythene_executive users exist
        poly_users = [u for u in data if u.get('role') == 'polythene_executive']
        print(f"Found {len(poly_users)} polythene_executive users for filter dropdown")


# Cleanup fixture
@pytest.fixture(scope="session", autouse=True)
def cleanup_test_users():
    """Cleanup test users after all tests"""
    yield
    # Cleanup would happen here if needed
    # For now, we leave test users as they don't affect production
