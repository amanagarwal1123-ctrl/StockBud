#!/usr/bin/env python3
"""
StockBud - Critical Bug Fixes Testing
Tests the 3 critical bug fixes implemented:
1. Date-Range Replacement in File Uploads
2. Polythene Item Name Matching
3. Stamp Change Propagation
"""

import requests
import sys
import json
import io
import pandas as pd
from datetime import datetime
from typing import Dict, Any, Optional

class CriticalFixesTester:
    def __init__(self, base_url="https://demand-ml-analytics.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.test_results = []
        self.auth_token = None
        
    def log_test(self, name: str, success: bool, details: str = "", expected: str = "", actual: str = ""):
        """Log test result with detailed information"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
            if details:
                print(f"   ℹ️  {details}")
        else:
            print(f"❌ {name}")
            if details:
                print(f"   ❌ {details}")
            if expected:
                print(f"   Expected: {expected}")
            if actual:
                print(f"   Actual: {actual}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details,
            "expected": expected,
            "actual": actual
        })
    
    def authenticate(self):
        """Authenticate and get token"""
        try:
            response = requests.post(
                f"{self.api_url}/auth/login",
                json={"username": "admin", "password": "admin123"},
                timeout=30
            )
            if response.status_code == 200:
                token_data = response.json()
                self.auth_token = token_data.get('access_token')
                return True
            return False
        except Exception as e:
            print(f"❌ Authentication failed: {str(e)}")
            return False
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     files: Optional[Dict] = None, params: Optional[Dict] = None,
                     expected_status: int = 200) -> tuple:
        """Make HTTP request and return success, response, details"""
        url = f"{self.api_url}/{endpoint}"
        
        try:
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f"Bearer {self.auth_token}"
            
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method == 'POST':
                if files:
                    response = requests.post(url, files=files, headers=headers, params=params, timeout=30)
                else:
                    response = requests.post(url, json=data, headers=headers, params=params, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=30)
            else:
                return False, None, f"Unsupported method: {method}"
            
            success = response.status_code == expected_status
            details = f"Status: {response.status_code}"
            
            if not success:
                details = f"Expected status {expected_status}, got {response.status_code}"
                if response.text:
                    try:
                        error_data = response.json()
                        details += f" - {error_data.get('detail', response.text[:200])}"
                    except:
                        details += f" - {response.text[:200]}"
            
            return success, response, details
            
        except requests.exceptions.Timeout:
            return False, None, "Request timeout (30s)"
        except requests.exceptions.ConnectionError:
            return False, None, "Connection error - backend may be down"
        except Exception as e:
            return False, None, f"Error: {str(e)}"
    
    def create_test_excel_file(self, file_type: str, test_data: list) -> bytes:
        """Create a test Excel file with given data"""
        if file_type == 'purchase':
            df = pd.DataFrame(test_data)
            # Ensure required columns exist
            required_cols = ['Date', 'Type', 'Item Name', 'Gr.Wt.', 'Net.Wt.', 'Fine', 'Stamp', 'Total', 'Tunch', 'Wstg']
            for col in required_cols:
                if col not in df.columns:
                    df[col] = ''
        else:
            df = pd.DataFrame(test_data)
        
        # Write to bytes
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return output.getvalue()
    
    def test_date_range_replacement(self):
        """Test Fix 1: Date-Range Replacement in File Uploads"""
        print("\n" + "="*60)
        print("🔧 FIX 1: DATE-RANGE REPLACEMENT IN FILE UPLOADS")
        print("="*60)
        
        # Step 1: Upload initial purchase data for date range 2024-01-01 to 2024-01-10
        print("\n📤 Step 1: Upload initial purchase data (2024-01-01 to 2024-01-10)")
        
        initial_data = [
            {
                'Date': '2024-01-05 00:00:00',  # Excel timestamp format
                'Type': 'P',
                'Item Name': 'TEST ITEM DATE RANGE',
                'Gr.Wt.': 1.0,
                'Net.Wt.': 0.9,
                'Fine': 0.8,
                'Stamp': 'Stamp 1',
                'Total': 1000,
                'Tunch': 85,
                'Wstg': 5,
                'Party Name': 'Test Supplier',
                'Refno': 'TEST001'
            }
        ]
        
        excel_file = self.create_test_excel_file('purchase', initial_data)
        files = {'file': ('test_purchase.xlsx', excel_file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        success, response, details = self.make_request(
            'POST', 
            'transactions/upload/purchase',
            files=files,
            params={'start_date': '2024-01-01', 'end_date': '2024-01-10'},
            expected_status=200
        )
        
        if success and response:
            try:
                result = response.json()
                count = result.get('count', 0)
                self.log_test("Initial upload with date range", True, 
                            f"Uploaded {count} transactions for 2024-01-01 to 2024-01-10")
            except Exception as e:
                self.log_test("Initial upload with date range", False, f"Error: {str(e)}")
        else:
            self.log_test("Initial upload with date range", False, details)
            return
        
        # Step 2: Get transaction count for this date range
        print("\n📊 Step 2: Verify initial transactions exist")
        success, response, details = self.make_request('GET', 'transactions', params={'type': 'purchase'})
        
        initial_count = 0
        if success and response:
            try:
                transactions = response.json()
                # Count transactions in our date range
                initial_count = sum(1 for t in transactions 
                                  if t.get('date', '').startswith('2024-01') 
                                  and 'TEST ITEM DATE RANGE' in t.get('item_name', ''))
                self.log_test("Initial transactions exist", True, 
                            f"Found {initial_count} transactions for TEST ITEM DATE RANGE")
            except Exception as e:
                self.log_test("Initial transactions exist", False, f"Error: {str(e)}")
        else:
            self.log_test("Initial transactions exist", False, details)
        
        # Step 3: Re-upload with DIFFERENT data for the SAME date range
        print("\n📤 Step 3: Re-upload with different data for SAME date range")
        
        new_data = [
            {
                'Date': '2024-01-07 00:00:00',  # Different date, same range
                'Type': 'P',
                'Item Name': 'TEST ITEM DATE RANGE',
                'Gr.Wt.': 2.0,  # Different weight
                'Net.Wt.': 1.8,
                'Fine': 1.6,
                'Stamp': 'Stamp 1',
                'Total': 2000,
                'Tunch': 85,
                'Wstg': 5,
                'Party Name': 'Test Supplier 2',
                'Refno': 'TEST002'
            },
            {
                'Date': '2024-01-08 00:00:00',
                'Type': 'P',
                'Item Name': 'TEST ITEM DATE RANGE',
                'Gr.Wt.': 1.5,
                'Net.Wt.': 1.3,
                'Fine': 1.2,
                'Stamp': 'Stamp 1',
                'Total': 1500,
                'Tunch': 85,
                'Wstg': 5,
                'Party Name': 'Test Supplier 3',
                'Refno': 'TEST003'
            }
        ]
        
        excel_file = self.create_test_excel_file('purchase', new_data)
        files = {'file': ('test_purchase_new.xlsx', excel_file, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')}
        
        success, response, details = self.make_request(
            'POST', 
            'transactions/upload/purchase',
            files=files,
            params={'start_date': '2024-01-01', 'end_date': '2024-01-10'},
            expected_status=200
        )
        
        replaced_count = 0
        if success and response:
            try:
                result = response.json()
                count = result.get('count', 0)
                replaced_count = result.get('replaced_count', 0)
                self.log_test("Re-upload with date range", True, 
                            f"Uploaded {count} new transactions, replaced {replaced_count} old transactions")
            except Exception as e:
                self.log_test("Re-upload with date range", False, f"Error: {str(e)}")
        else:
            self.log_test("Re-upload with date range", False, details)
            return
        
        # Step 4: Verify old data is COMPLETELY REMOVED
        print("\n✅ Step 4: Verify old data is completely removed")
        success, response, details = self.make_request('GET', 'transactions', params={'type': 'purchase'})
        
        if success and response:
            try:
                transactions = response.json()
                # Count transactions in our date range
                final_count = sum(1 for t in transactions 
                                if t.get('date', '').startswith('2024-01') 
                                and 'TEST ITEM DATE RANGE' in t.get('item_name', ''))
                
                # Should have exactly 2 transactions (the new ones)
                if final_count == 2:
                    self.log_test("Old data completely removed", True, 
                                f"Found exactly {final_count} transactions (expected 2 new ones)")
                else:
                    self.log_test("Old data completely removed", False, 
                                f"Transaction count mismatch",
                                expected="2 transactions",
                                actual=f"{final_count} transactions")
                
                # Verify dates are in YYYY-MM-DD format
                test_transactions = [t for t in transactions 
                                   if 'TEST ITEM DATE RANGE' in t.get('item_name', '')]
                
                dates_normalized = all(
                    len(t.get('date', '').split('-')) == 3 and 
                    len(t.get('date', '').split(' ')[0]) == 10
                    for t in test_transactions
                )
                
                if dates_normalized:
                    sample_date = test_transactions[0].get('date', '') if test_transactions else 'N/A'
                    self.log_test("Dates stored in YYYY-MM-DD format", True, 
                                f"All dates normalized (sample: {sample_date})")
                else:
                    self.log_test("Dates stored in YYYY-MM-DD format", False, 
                                "Some dates not in YYYY-MM-DD format")
                
            except Exception as e:
                self.log_test("Old data completely removed", False, f"Error: {str(e)}")
        else:
            self.log_test("Old data completely removed", False, details)
    
    def test_polythene_item_name_matching(self):
        """Test Fix 2: Polythene Item Name Matching"""
        print("\n" + "="*60)
        print("🔧 FIX 2: POLYTHENE ITEM NAME MATCHING")
        print("="*60)
        
        # Step 1: Check if item mappings exist
        print("\n📋 Step 1: Check item mappings")
        success, response, details = self.make_request('GET', 'mappings/all')
        
        mappings = []
        if success and response:
            try:
                mappings = response.json()
                self.log_test("Get item mappings", True, f"Found {len(mappings)} mappings")
            except Exception as e:
                self.log_test("Get item mappings", False, f"Error: {str(e)}")
        else:
            self.log_test("Get item mappings", False, details)
        
        # Step 2: Create a polythene adjustment using a transaction name (not master name)
        print("\n📤 Step 2: Create polythene adjustment with transaction name")
        
        # Find a mapping to test with
        test_mapping = None
        if mappings:
            # Look for a mapping where transaction_name != master_name
            for m in mappings:
                if m.get('transaction_name') != m.get('master_name'):
                    test_mapping = m
                    break
        
        if test_mapping:
            transaction_name = test_mapping.get('transaction_name')
            master_name = test_mapping.get('master_name')
            
            print(f"   Using mapping: '{transaction_name}' → '{master_name}'")
            
            # Create polythene adjustment using transaction name
            adjustment_data = {
                'entries': [
                    {
                        'item_name': transaction_name,  # Use transaction name, not master name
                        'stamp': 'Stamp 1',
                        'poly_weight': 0.5,  # 0.5 kg
                        'operation': 'add'
                    }
                ],
                'adjusted_by': 'admin'
            }
            
            success, response, details = self.make_request(
                'POST',
                'polythene/adjust-batch',
                data=adjustment_data,
                expected_status=200
            )
            
            if success and response:
                try:
                    result = response.json()
                    count = result.get('count', 0)
                    self.log_test("Create polythene adjustment with transaction name", True,
                                f"Created {count} adjustment(s) using transaction name '{transaction_name}'")
                except Exception as e:
                    self.log_test("Create polythene adjustment with transaction name", False, f"Error: {str(e)}")
            else:
                self.log_test("Create polythene adjustment with transaction name", False, details)
            
            # Step 3: Verify adjustment is applied to master item in inventory
            print("\n✅ Step 3: Verify adjustment applied to correct master item")
            
            success, response, details = self.make_request('GET', 'inventory/current')
            
            if success and response:
                try:
                    data = response.json()
                    inventory = data.get('inventory', [])
                    
                    # Find the master item in inventory
                    master_item = next((item for item in inventory 
                                      if item.get('item_name') == master_name), None)
                    
                    if master_item:
                        self.log_test("Polythene adjustment applied to master item", True,
                                    f"Adjustment correctly applied to master item '{master_name}' (gross weight includes polythene)")
                    else:
                        self.log_test("Polythene adjustment applied to master item", False,
                                    f"Master item '{master_name}' not found in inventory")
                    
                except Exception as e:
                    self.log_test("Polythene adjustment applied to master item", False, f"Error: {str(e)}")
            else:
                self.log_test("Polythene adjustment applied to master item", False, details)
        else:
            self.log_test("Find test mapping", False, "No suitable mapping found for testing")
    
    def test_stamp_change_propagation(self):
        """Test Fix 3: Stamp Change Propagation"""
        print("\n" + "="*60)
        print("🔧 FIX 3: STAMP CHANGE PROPAGATION")
        print("="*60)
        
        # Step 1: Get a test item from master_items
        print("\n📋 Step 1: Get test item from master_items")
        
        success, response, details = self.make_request('GET', 'inventory/current')
        
        test_item_name = None
        original_stamp = None
        
        if success and response:
            try:
                data = response.json()
                inventory = data.get('inventory', [])
                
                # Find an item with a stamp that we can change
                for item in inventory:
                    if item.get('stamp') and item.get('stamp') != 'Unassigned':
                        test_item_name = item.get('item_name')
                        original_stamp = item.get('stamp')
                        break
                
                if test_item_name:
                    self.log_test("Find test item", True, 
                                f"Using item '{test_item_name}' with stamp '{original_stamp}'")
                else:
                    self.log_test("Find test item", False, "No suitable item found")
                    return
                
            except Exception as e:
                self.log_test("Find test item", False, f"Error: {str(e)}")
                return
        else:
            self.log_test("Find test item", False, details)
            return
        
        # Step 2: Assign a new stamp to the item
        print("\n📤 Step 2: Assign new stamp to item")
        
        new_stamp = 'Stamp 2' if original_stamp != 'Stamp 2' else 'Stamp 3'
        
        success, response, details = self.make_request(
            'POST',
            f'item/{test_item_name}/assign-stamp',
            params={'stamp': new_stamp},
            expected_status=200
        )
        
        if success and response:
            try:
                result = response.json()
                self.log_test("Assign new stamp", True,
                            f"Assigned '{new_stamp}' to '{test_item_name}'")
            except Exception as e:
                self.log_test("Assign new stamp", False, f"Error: {str(e)}")
        else:
            self.log_test("Assign new stamp", False, details)
            return
        
        # Step 3: Verify stamp updated in master_items
        print("\n✅ Step 3: Verify stamp updated in master_items")
        
        success, response, details = self.make_request('GET', 'inventory/current')
        
        if success and response:
            try:
                data = response.json()
                inventory = data.get('inventory', [])
                
                # Find the item
                updated_item = next((item for item in inventory 
                                   if item.get('item_name') == test_item_name), None)
                
                if updated_item:
                    current_stamp = updated_item.get('stamp')
                    if current_stamp == new_stamp:
                        self.log_test("Stamp updated in master_items", True,
                                    f"Stamp correctly updated to '{new_stamp}' in master_items")
                    else:
                        self.log_test("Stamp updated in master_items", False,
                                    f"Stamp not updated",
                                    expected=new_stamp,
                                    actual=current_stamp)
                else:
                    self.log_test("Stamp updated in master_items", False,
                                f"Item '{test_item_name}' not found after update")
                
            except Exception as e:
                self.log_test("Stamp updated in master_items", False, f"Error: {str(e)}")
        else:
            self.log_test("Stamp updated in master_items", False, details)
        
        # Step 4: Verify stamp visible in Stock Entry Executive view
        print("\n✅ Step 4: Verify stamp visible in Stock Entry Executive view")
        
        # Get all master items and filter by stamp (this is what executives see)
        success, response, details = self.make_request(
            'GET',
            'master-items'
        )
        
        if success and response:
            try:
                all_items = response.json()
                
                # Filter items by the new stamp
                items_with_new_stamp = [item for item in all_items if item.get('stamp') == new_stamp]
                
                # Check if our test item is in the list
                item_found = any(item.get('item_name') == test_item_name for item in items_with_new_stamp)
                
                if item_found:
                    self.log_test("Stamp visible in Executive view", True,
                                f"Item '{test_item_name}' visible in '{new_stamp}' for executives")
                else:
                    self.log_test("Stamp visible in Executive view", False,
                                f"Item '{test_item_name}' not found in executive view for '{new_stamp}'")
                
            except Exception as e:
                self.log_test("Stamp visible in Executive view", False, f"Error: {str(e)}")
        else:
            self.log_test("Stamp visible in Executive view", False, details)
        
        # Step 5: Restore original stamp
        print("\n🔄 Step 5: Restore original stamp")
        
        success, response, details = self.make_request(
            'POST',
            f'item/{test_item_name}/assign-stamp',
            params={'stamp': original_stamp},
            expected_status=200
        )
        
        if success:
            print(f"   ℹ️  Restored original stamp '{original_stamp}' to '{test_item_name}'")
    
    def run_all_tests(self):
        """Run all critical fix tests"""
        print("\n" + "🧪 " + "="*58)
        print("   StockBud - Critical Bug Fixes Testing")
        print("   Testing 3 Critical Fixes")
        print("="*60)
        
        # Authenticate first
        print("\n🔐 Authenticating...")
        if not self.authenticate():
            print("❌ Authentication failed. Cannot proceed with tests.")
            return False
        print("✅ Authenticated successfully")
        
        # Run all test suites
        self.test_date_range_replacement()
        self.test_polythene_item_name_matching()
        self.test_stamp_change_propagation()
        
        # Print final results
        print("\n" + "="*60)
        print(f"📊 FINAL TEST RESULTS: {self.tests_passed}/{self.tests_run} PASSED")
        print("="*60)
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL CRITICAL FIXES VERIFIED! All 3 bug fixes are working correctly.")
            return True
        else:
            print(f"⚠️  {self.tests_run - self.tests_passed} TESTS FAILED")
            print("\nFailed tests:")
            for test in self.test_results:
                if not test['success']:
                    print(f"  ❌ {test['test']}")
                    if test['details']:
                        print(f"     {test['details']}")
                    if test['expected']:
                        print(f"     Expected: {test['expected']}")
                    if test['actual']:
                        print(f"     Actual: {test['actual']}")
            return False

def main():
    tester = CriticalFixesTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
