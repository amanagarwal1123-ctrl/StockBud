#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime
import tempfile
import pandas as pd
from io import BytesIO

class JewelryInventoryTester:
    def __init__(self, base_url="https://inventory-sync-63.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def test_api_endpoint(self, method, endpoint, expected_status=200, data=None, files=None):
        """Test a single API endpoint"""
        url = f"{self.api_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, timeout=30)
                else:
                    response = requests.post(url, json=data, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, timeout=30)
            
            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            if not success:
                details += f", Expected: {expected_status}"
                if response.text:
                    details += f", Response: {response.text[:200]}"
            
            return success, response, details
        except Exception as e:
            return False, None, f"Error: {str(e)}"

    def create_test_excel_files(self):
        """Create test Excel files for upload testing"""
        # Purchase file
        purchase_data = {
            'Date': ['2024-01-01', '2024-01-02'],
            'Refno': ['P001', 'P002'],
            'Party Name': ['Supplier A', 'Supplier B'],
            'Item Name': ['Gold Ring', 'Silver Necklace'],
            'Stamp': ['GR001', 'SN001'],
            'Tag.No.': ['T001', 'T002'],
            'Gr.Wt.': [10.5, 25.3],
            'Net.Wt.': [9.8, 24.1],
            'Fine Sil.': [8.5, 22.0],
            'Lbr. Wt/Rs': [100, 200],
            'Dia.Wt.': [0.5, 1.2],
            'Stn.Wt.': [0.2, 0.1],
            'Total Pc': [1, 1]
        }
        
        # Sale file
        sale_data = {
            'Item Name': ['Gold Ring', 'Silver Necklace'],
            'Gr.Wt.': [2.5, 5.3],
            'Less': [2.3, 5.0],
            'Fine Sil.': [2.0, 4.5],
            'Fine Total': [50, 100],
            'Dia.Wt.': [0.1, 0.2],
            'Stn.Wt.': [0.05, 0.1],
            'Pc': [1, 1]
        }
        
        # Physical inventory file
        physical_data = {
            'Item Name': ['Gold Ring', 'Silver Necklace', 'Diamond Earrings'],
            'Stamp': ['GR001', 'SN001', ''],
            'Gross Weight': [8.0, 20.0, 15.5],
            'Poly Weight': [0.5, 1.0, 0.8],
            'Net Weight': [7.5, 19.0, 14.7]
        }
        
        # Create Excel files in memory
        purchase_buffer = BytesIO()
        sale_buffer = BytesIO()
        physical_buffer = BytesIO()
        
        pd.DataFrame(purchase_data).to_excel(purchase_buffer, index=False)
        pd.DataFrame(sale_data).to_excel(sale_buffer, index=False)
        pd.DataFrame(physical_data).to_excel(physical_buffer, index=False)
        
        purchase_buffer.seek(0)
        sale_buffer.seek(0)
        physical_buffer.seek(0)
        
        return purchase_buffer, sale_buffer, physical_buffer

    def run_all_tests(self):
        """Run comprehensive API tests"""
        print("🧪 Starting Jewelry Inventory Management API Tests")
        print("=" * 60)
        
        # Test 1: Health check - Get stats (should work even with empty DB)
        success, response, details = self.test_api_endpoint('GET', 'stats')
        self.log_test("GET /api/stats", success, details)
        
        # Test 2: Clear existing data for clean test
        success, response, details = self.test_api_endpoint('DELETE', 'transactions/all')
        self.log_test("DELETE /api/transactions/all", success, details)
        
        # Test 3: Get empty transactions
        success, response, details = self.test_api_endpoint('GET', 'transactions')
        self.log_test("GET /api/transactions (empty)", success, details)
        
        # Test 4: Get empty book inventory
        success, response, details = self.test_api_endpoint('GET', 'inventory/book')
        self.log_test("GET /api/inventory/book (empty)", success, details)
        
        # Create test Excel files
        try:
            purchase_file, sale_file, physical_file = self.create_test_excel_files()
            
            # Test 5: Upload purchase file
            files = {'file': ('purchase.xlsx', purchase_file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            success, response, details = self.test_api_endpoint('POST', 'transactions/upload/purchase', 200, files=files)
            self.log_test("POST /api/transactions/upload/purchase", success, details)
            
            # Test 6: Upload sale file
            files = {'file': ('sale.xlsx', sale_file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            success, response, details = self.test_api_endpoint('POST', 'transactions/upload/sale', 200, files=files)
            self.log_test("POST /api/transactions/upload/sale", success, details)
            
            # Test 7: Get transactions after upload
            success, response, details = self.test_api_endpoint('GET', 'transactions')
            self.log_test("GET /api/transactions (with data)", success, details)
            
            # Test 8: Get book inventory after transactions
            success, response, details = self.test_api_endpoint('GET', 'inventory/book')
            self.log_test("GET /api/inventory/book (calculated)", success, details)
            
            # Test 9: Upload physical inventory
            files = {'file': ('physical.xlsx', physical_file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
            success, response, details = self.test_api_endpoint('POST', 'inventory/physical/upload', 200, files=files)
            self.log_test("POST /api/inventory/physical/upload", success, details)
            
            # Test 10: Get physical inventory
            success, response, details = self.test_api_endpoint('GET', 'inventory/physical')
            self.log_test("GET /api/inventory/physical", success, details)
            
            # Test 11: Run inventory matching
            success, response, details = self.test_api_endpoint('POST', 'inventory/match')
            self.log_test("POST /api/inventory/match", success, details)
            
            # Test 12: Get snapshots
            success, response, details = self.test_api_endpoint('GET', 'snapshots')
            self.log_test("GET /api/snapshots", success, details)
            
            # Test 13: Assign stamp to unmatched item
            stamp_data = {"item_name": "Diamond Earrings", "stamp": "DE001"}
            success, response, details = self.test_api_endpoint('POST', 'inventory/assign-stamp', 200, data=stamp_data)
            self.log_test("POST /api/inventory/assign-stamp", success, details)
            
            # Test 14: Get movement analytics
            success, response, details = self.test_api_endpoint('GET', 'analytics/movement')
            self.log_test("GET /api/analytics/movement", success, details)
            
            # Test 15: Get poly exceptions
            success, response, details = self.test_api_endpoint('GET', 'analytics/poly-exceptions')
            self.log_test("GET /api/analytics/poly-exceptions", success, details)
            
            # Test 16: Get updated stats
            success, response, details = self.test_api_endpoint('GET', 'stats')
            self.log_test("GET /api/stats (final)", success, details)
            
        except Exception as e:
            self.log_test("File creation/upload tests", False, f"Error creating test files: {str(e)}")
        
        # Print results
        print("\n" + "=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed! Backend API is working correctly.")
            return True
        else:
            print("⚠️  Some tests failed. Check the details above.")
            failed_tests = [test for test in self.test_results if not test['success']]
            print("\nFailed tests:")
            for test in failed_tests:
                print(f"  - {test['test']}: {test['details']}")
            return False

def main():
    tester = JewelryInventoryTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())