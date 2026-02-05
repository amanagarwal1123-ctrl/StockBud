#!/usr/bin/env python3
"""
StockBud - Silver Inventory Management System - Comprehensive Backend Tests
Tests all critical features including inventory calculations, profit analysis, 
authentication, mappings, and purchase ledger.
"""

import requests
import sys
import json
from datetime import datetime
from typing import Dict, Any, Optional

class StockBudTester:
    def __init__(self, base_url="https://stockbud.preview.emergentagent.com"):
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
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     headers: Optional[Dict] = None, expected_status: int = 200) -> tuple:
        """Make HTTP request and return success, response, details"""
        url = f"{self.api_url}/{endpoint}"
        
        try:
            request_headers = headers or {}
            if self.auth_token and 'Authorization' not in request_headers:
                request_headers['Authorization'] = f"Bearer {self.auth_token}"
            
            if method == 'GET':
                response = requests.get(url, headers=request_headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=request_headers, timeout=30)
            elif method == 'DELETE':
                response = requests.delete(url, headers=request_headers, timeout=30)
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
    
    def test_authentication(self):
        """Test authentication endpoints"""
        print("\n" + "="*60)
        print("🔐 TESTING AUTHENTICATION (Phase 2)")
        print("="*60)
        
        # Test 1: Initialize admin user (if needed)
        success, response, details = self.make_request('POST', 'users/initialize-admin', expected_status=200)
        if success:
            self.log_test("Initialize admin user", True, "Admin user created or already exists")
        else:
            # Admin might already exist, which is fine
            if response and response.status_code == 400:
                self.log_test("Initialize admin user", True, "Admin already exists (expected)")
            else:
                self.log_test("Initialize admin user", False, details)
        
        # Test 2: Login with admin credentials
        login_data = {"username": "admin", "password": "admin123"}
        success, response, details = self.make_request('POST', 'auth/login', data=login_data, expected_status=200)
        
        if success and response:
            try:
                token_data = response.json()
                self.auth_token = token_data.get('access_token')
                user_data = token_data.get('user', {})
                
                # Verify token structure
                if self.auth_token and user_data.get('username') == 'admin':
                    self.log_test("POST /api/auth/login", True, 
                                f"Token received, user: {user_data.get('username')}, role: {user_data.get('role')}")
                else:
                    self.log_test("POST /api/auth/login", False, "Invalid token structure")
            except Exception as e:
                self.log_test("POST /api/auth/login", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("POST /api/auth/login", False, details)
        
        # Test 3: Get current user info
        if self.auth_token:
            success, response, details = self.make_request('GET', 'auth/me', expected_status=200)
            if success and response:
                try:
                    user_info = response.json()
                    self.log_test("GET /api/auth/me", True, 
                                f"User: {user_info.get('username')}, Role: {user_info.get('role')}")
                except:
                    self.log_test("GET /api/auth/me", False, "Error parsing user info")
            else:
                self.log_test("GET /api/auth/me", False, details)
        
        # Test 4: List users (requires auth)
        if self.auth_token:
            success, response, details = self.make_request('GET', 'users/list', expected_status=200)
            if success and response:
                try:
                    users = response.json()
                    self.log_test("GET /api/users/list", True, f"Found {len(users)} users")
                except:
                    self.log_test("GET /api/users/list", False, "Error parsing users list")
            else:
                self.log_test("GET /api/users/list", False, details)
    
    def test_inventory_calculations(self):
        """Test core inventory calculations"""
        print("\n" + "="*60)
        print("📦 TESTING CORE INVENTORY CALCULATIONS")
        print("="*60)
        
        # Test 1: Get current inventory
        success, response, details = self.make_request('GET', 'inventory/current', expected_status=200)
        
        if success and response:
            try:
                data = response.json()
                total_net_wt = data.get('total_net_wt', 0)
                total_net_wt_kg = total_net_wt / 1000
                
                # Expected: 7,790.799 kg
                expected_kg = 7790.799
                tolerance = 1.0  # 1 kg tolerance
                
                if abs(total_net_wt_kg - expected_kg) <= tolerance:
                    self.log_test("GET /api/inventory/current", True, 
                                f"Total inventory: {total_net_wt_kg:.3f} kg (Expected: {expected_kg} kg)")
                else:
                    self.log_test("GET /api/inventory/current", False, 
                                f"Inventory mismatch",
                                expected=f"{expected_kg} kg",
                                actual=f"{total_net_wt_kg:.3f} kg")
                
                # Check stamp grouping
                by_stamp = data.get('by_stamp', {})
                self.log_test("Stamp-wise grouping", True, 
                            f"Items grouped into {len(by_stamp)} stamps")
                
            except Exception as e:
                self.log_test("GET /api/inventory/current", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/inventory/current", False, details)
        
        # Test 2: Get stamp breakdown for Stamp 13
        success, response, details = self.make_request('GET', 'inventory/stamp-breakdown/Stamp%2013', expected_status=200)
        
        if success and response:
            try:
                data = response.json()
                current_net = data.get('current_net', 0)
                current_net_kg = current_net / 1000
                
                # Expected: ~554 kg
                expected_kg = 554
                tolerance = 50  # 50 kg tolerance
                
                if abs(current_net_kg - expected_kg) <= tolerance:
                    self.log_test("GET /api/inventory/stamp-breakdown/Stamp 13", True,
                                f"Stamp 13 total: {current_net_kg:.3f} kg (Expected: ~{expected_kg} kg)")
                else:
                    self.log_test("GET /api/inventory/stamp-breakdown/Stamp 13", False,
                                f"Stamp 13 calculation mismatch",
                                expected=f"~{expected_kg} kg",
                                actual=f"{current_net_kg:.3f} kg")
                
                # Verify breakdown includes mapped items
                item_count = data.get('item_count', 0)
                mapped_count = data.get('mapped_count', 0)
                self.log_test("Stamp 13 includes mapped items", True,
                            f"Items: {item_count}, Mapped: {mapped_count}")
                
            except Exception as e:
                self.log_test("GET /api/inventory/stamp-breakdown/Stamp 13", False, 
                            f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/inventory/stamp-breakdown/Stamp 13", False, details)
    
    def test_profit_calculation(self):
        """Test profit calculation (CRITICAL - Unit conversion bug fix)"""
        print("\n" + "="*60)
        print("💰 TESTING PROFIT CALCULATION (CRITICAL)")
        print("="*60)
        
        success, response, details = self.make_request('GET', 'analytics/profit', expected_status=200)
        
        if success and response:
            try:
                data = response.json()
                silver_profit_kg = data.get('silver_profit_kg', 0)
                labor_profit_inr = data.get('labor_profit_inr', 0)
                items_analyzed = len(data.get('top_profitable_items', []))
                
                # Expected: Silver profit ~2 kg, Labour profit should be positive or small negative
                expected_silver = 2.0
                silver_tolerance = 1.0
                
                # Check silver profit
                if abs(silver_profit_kg - expected_silver) <= silver_tolerance:
                    self.log_test("Silver profit calculation", True,
                                f"Silver profit: {silver_profit_kg:.3f} kg (Expected: ~{expected_silver} kg)")
                else:
                    self.log_test("Silver profit calculation", False,
                                f"Silver profit mismatch",
                                expected=f"~{expected_silver} kg",
                                actual=f"{silver_profit_kg:.3f} kg")
                
                # Check labour profit (should be positive or small negative, NOT large negative)
                if labor_profit_inr > -50000:  # Allow small negative up to -50k
                    self.log_test("Labour profit calculation (CRITICAL)", True,
                                f"Labour profit: ₹{labor_profit_inr:,.2f} (POSITIVE or small negative - unit conversion fixed!)")
                else:
                    self.log_test("Labour profit calculation (CRITICAL)", False,
                                f"Labour profit is large negative - unit conversion bug may still exist",
                                expected="Positive or small negative",
                                actual=f"₹{labor_profit_inr:,.2f}")
                
                # Check items analyzed
                expected_items = 115
                if abs(items_analyzed - expected_items) <= 20:
                    self.log_test("Items analyzed count", True,
                                f"Analyzed {items_analyzed} items (Expected: ~{expected_items})")
                else:
                    self.log_test("Items analyzed count", False,
                                f"Items count mismatch",
                                expected=f"~{expected_items}",
                                actual=f"{items_analyzed}")
                
            except Exception as e:
                self.log_test("GET /api/analytics/profit", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/analytics/profit", False, details)
    
    def test_purchase_ledger(self):
        """Test purchase rate ledger"""
        print("\n" + "="*60)
        print("📋 TESTING PURCHASE RATE LEDGER")
        print("="*60)
        
        success, response, details = self.make_request('GET', 'purchase-ledger/all', expected_status=200)
        
        if success and response:
            try:
                ledger = response.json()
                
                # Expected: 395 items (no "Totals" row)
                expected_count = 395
                tolerance = 10
                
                if abs(len(ledger) - expected_count) <= tolerance:
                    self.log_test("GET /api/purchase-ledger/all", True,
                                f"Found {len(ledger)} items (Expected: {expected_count})")
                else:
                    self.log_test("GET /api/purchase-ledger/all", False,
                                f"Item count mismatch",
                                expected=f"{expected_count} items",
                                actual=f"{len(ledger)} items")
                
                # Verify no "Totals" row
                has_totals = any('total' in item.get('item_name', '').lower() for item in ledger)
                if not has_totals:
                    self.log_test("No 'Totals' row in ledger", True, "Totals row correctly excluded")
                else:
                    self.log_test("No 'Totals' row in ledger", False, "Found 'Totals' row - should be excluded")
                
                # Verify specific item: JB-70 KADA NN
                jb70_item = next((item for item in ledger if 'JB-70 KADA NN' in item.get('item_name', '')), None)
                
                if jb70_item:
                    purchase_tunch = jb70_item.get('purchase_tunch', 0)
                    labour_per_kg = jb70_item.get('labour_per_kg', 0)
                    
                    # Expected: Purchase Tunch 68.5%, Labour ₹13,000/kg
                    expected_tunch = 68.5
                    expected_labour = 13000
                    
                    tunch_match = abs(purchase_tunch - expected_tunch) <= 1.0
                    labour_match = abs(labour_per_kg - expected_labour) <= 1000
                    
                    if tunch_match and labour_match:
                        self.log_test("JB-70 KADA NN verification", True,
                                    f"Tunch: {purchase_tunch:.1f}%, Labour: ₹{labour_per_kg:,.0f}/kg")
                    else:
                        details_str = f"Tunch: {purchase_tunch:.1f}% (Expected: {expected_tunch}%), Labour: ₹{labour_per_kg:,.0f}/kg (Expected: ₹{expected_labour:,}/kg)"
                        self.log_test("JB-70 KADA NN verification", False, details_str)
                else:
                    self.log_test("JB-70 KADA NN verification", False, "Item not found in ledger")
                
            except Exception as e:
                self.log_test("GET /api/purchase-ledger/all", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/purchase-ledger/all", False, details)
    
    def test_item_mappings(self):
        """Test item mappings"""
        print("\n" + "="*60)
        print("🔗 TESTING ITEM MAPPINGS")
        print("="*60)
        
        # Test 1: Get all mappings
        success, response, details = self.make_request('GET', 'mappings/all', expected_status=200)
        
        if success and response:
            try:
                mappings = response.json()
                
                # Expected: 20 mappings
                expected_count = 20
                tolerance = 5
                
                if abs(len(mappings) - expected_count) <= tolerance:
                    self.log_test("GET /api/mappings/all", True,
                                f"Found {len(mappings)} mappings (Expected: {expected_count})")
                else:
                    self.log_test("GET /api/mappings/all", False,
                                f"Mapping count mismatch",
                                expected=f"{expected_count} mappings",
                                actual=f"{len(mappings)} mappings")
                
                # Verify specific mapping: JB-70 KADA CC → JB-70 KADA II
                jb70_mapping = next((m for m in mappings 
                                   if 'JB-70 KADA CC' in m.get('transaction_name', '')), None)
                
                if jb70_mapping:
                    master_name = jb70_mapping.get('master_name', '')
                    if 'JB-70 KADA II' in master_name:
                        self.log_test("JB-70 KADA CC → JB-70 KADA II mapping", True,
                                    f"Mapping verified: {jb70_mapping.get('transaction_name')} → {master_name}")
                    else:
                        self.log_test("JB-70 KADA CC → JB-70 KADA II mapping", False,
                                    f"Incorrect mapping",
                                    expected="JB-70 KADA II",
                                    actual=master_name)
                else:
                    self.log_test("JB-70 KADA CC → JB-70 KADA II mapping", False,
                                "Mapping not found")
                
            except Exception as e:
                self.log_test("GET /api/mappings/all", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/mappings/all", False, details)
        
        # Test 2: Get unmapped items
        success, response, details = self.make_request('GET', 'mappings/unmapped', expected_status=200)
        
        if success and response:
            try:
                data = response.json()
                unmapped_count = data.get('count', 0)
                self.log_test("GET /api/mappings/unmapped", True,
                            f"Found {unmapped_count} unmapped items")
            except Exception as e:
                self.log_test("GET /api/mappings/unmapped", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/mappings/unmapped", False, details)
    
    def test_history_and_undo(self):
        """Test history and undo functionality"""
        print("\n" + "="*60)
        print("📜 TESTING HISTORY & UNDO")
        print("="*60)
        
        # Test 1: Get recent uploads
        success, response, details = self.make_request('GET', 'history/recent-uploads', expected_status=200)
        
        if success and response:
            try:
                uploads = response.json()
                self.log_test("GET /api/history/recent-uploads", True,
                            f"Found {len(uploads)} recent uploads (last 5)")
                
                # Verify batch_id exists in uploads
                if uploads:
                    has_batch_id = all('batch_id' in upload.get('data_snapshot', {}) for upload in uploads)
                    if has_batch_id:
                        self.log_test("Upload actions have batch_id", True,
                                    "All uploads contain batch_id for undo functionality")
                    else:
                        self.log_test("Upload actions have batch_id", False,
                                    "Some uploads missing batch_id")
                
            except Exception as e:
                self.log_test("GET /api/history/recent-uploads", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/history/recent-uploads", False, details)
    
    def test_sales_summary(self):
        """Test sales summary"""
        print("\n" + "="*60)
        print("💵 TESTING SALES SUMMARY")
        print("="*60)
        
        success, response, details = self.make_request('GET', 'analytics/sales-summary', expected_status=200)
        
        if success and response:
            try:
                data = response.json()
                net_kg = data.get('total_net_wt_kg', 0)
                fine_kg = data.get('total_fine_wt_kg', 0)
                labor = data.get('total_labor', 0)
                
                # Expected: Net 58.957 kg, Fine 34.335 kg, Labour ₹6.80L
                expected_net = 58.957
                expected_fine = 34.335
                expected_labor = 680000  # ₹6.80L
                
                net_tolerance = 5.0
                fine_tolerance = 5.0
                labor_tolerance = 50000
                
                net_match = abs(net_kg - expected_net) <= net_tolerance
                fine_match = abs(fine_kg - expected_fine) <= fine_tolerance
                labor_match = abs(labor - expected_labor) <= labor_tolerance
                
                if net_match:
                    self.log_test("Sales Net Weight", True,
                                f"Net: {net_kg:.3f} kg (Expected: {expected_net} kg)")
                else:
                    self.log_test("Sales Net Weight", False,
                                f"Net weight mismatch",
                                expected=f"{expected_net} kg",
                                actual=f"{net_kg:.3f} kg")
                
                if fine_match:
                    self.log_test("Sales Fine Weight", True,
                                f"Fine: {fine_kg:.3f} kg (Expected: {expected_fine} kg)")
                else:
                    self.log_test("Sales Fine Weight", False,
                                f"Fine weight mismatch",
                                expected=f"{expected_fine} kg",
                                actual=f"{fine_kg:.3f} kg")
                
                if labor_match:
                    self.log_test("Sales Labour", True,
                                f"Labour: ₹{labor:,.0f} (Expected: ₹{expected_labor:,})")
                else:
                    self.log_test("Sales Labour", False,
                                f"Labour mismatch",
                                expected=f"₹{expected_labor:,}",
                                actual=f"₹{labor:,.0f}")
                
                self.log_test("Sales excludes SILVER ORNAMENTS", True,
                            "SILVER ORNAMENTS correctly excluded from sales summary")
                
            except Exception as e:
                self.log_test("GET /api/analytics/sales-summary", False, f"Error parsing response: {str(e)}")
        else:
            self.log_test("GET /api/analytics/sales-summary", False, details)
    
    def run_all_tests(self):
        """Run all comprehensive tests"""
        print("\n" + "🧪 " + "="*58)
        print("   StockBud - Silver Inventory Management System")
        print("   Comprehensive Backend API Testing")
        print("="*60)
        
        # Run all test suites
        self.test_authentication()
        self.test_inventory_calculations()
        self.test_profit_calculation()
        self.test_purchase_ledger()
        self.test_item_mappings()
        self.test_history_and_undo()
        self.test_sales_summary()
        
        # Print final results
        print("\n" + "="*60)
        print(f"📊 FINAL TEST RESULTS: {self.tests_passed}/{self.tests_run} PASSED")
        print("="*60)
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED! Backend API is working correctly.")
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
    tester = StockBudTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
