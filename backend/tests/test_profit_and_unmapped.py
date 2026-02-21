"""
Test suite for Profit Analysis and Unmapped Items fixes (Iteration 13)
- Labour profit should be POSITIVE (~₹38L total)
- Individual items should have non-zero labor_profit_inr
- Sales summary total_labor should be non-zero (~₹62L)
- Unmapped items should NOT contain '136' or other purely numeric names
- Unmapped items should NOT contain test data patterns
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestHealthAndAuth:
    """Basic health checks"""
    
    def test_health_check(self):
        """Verify API is running"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        print("✓ Health check passed")


class TestProfitEndpoint:
    """Tests for GET /api/analytics/profit - Labour profit fix"""
    
    def test_profit_endpoint_returns_200(self):
        """Verify profit endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("✓ Profit endpoint returns 200")
    
    def test_profit_has_required_fields(self):
        """Verify profit response has required fields"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ['silver_profit_kg', 'labor_profit_inr', 'all_items', 'total_items_analyzed']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"✓ Profit response has all required fields: {required_fields}")
    
    def test_labor_profit_is_positive(self):
        """CRITICAL: Labour profit should be POSITIVE (was showing -₹1.05L - bug fix)"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200
        data = response.json()
        
        labor_profit = data.get('labor_profit_inr', 0)
        print(f"  Total labor_profit_inr: ₹{labor_profit:,.2f}")
        
        # Should be positive and substantial (expected ~₹38L based on agent notes)
        assert labor_profit > 0, f"Labour profit should be POSITIVE, got: {labor_profit}"
        print(f"✓ Labour profit is POSITIVE: ₹{labor_profit:,.2f}")
    
    def test_labor_profit_is_substantial(self):
        """Labour profit should be in reasonable range (expected ~₹38L)"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200
        data = response.json()
        
        labor_profit = data.get('labor_profit_inr', 0)
        
        # Should be at least ₹1L (100,000) given the business scale
        # Expected ~₹38L based on agent context
        assert labor_profit >= 100000, f"Labour profit seems too low: {labor_profit} (expected >= ₹1L)"
        print(f"✓ Labour profit is substantial: ₹{labor_profit:,.2f} (>= ₹1L)")
    
    def test_individual_items_have_nonzero_labor(self):
        """CRITICAL: Individual items should have non-zero labor_profit_inr (was all showing ₹0)"""
        response = requests.get(f"{BASE_URL}/api/analytics/profit")
        assert response.status_code == 200
        data = response.json()
        
        all_items = data.get('all_items', [])
        assert len(all_items) > 0, "No items in profit analysis"
        
        # Count items with non-zero labor profit
        items_with_labor = [item for item in all_items if abs(item.get('labor_profit_inr', 0)) > 0]
        percent_with_labor = (len(items_with_labor) / len(all_items)) * 100
        
        print(f"  Total items analyzed: {len(all_items)}")
        print(f"  Items with non-zero labor_profit_inr: {len(items_with_labor)} ({percent_with_labor:.1f}%)")
        
        # At least 20% of items should have non-zero labor profit
        assert len(items_with_labor) > 0, "No items have non-zero labor_profit_inr - BUG NOT FIXED"
        assert percent_with_labor >= 10, f"Only {percent_with_labor:.1f}% items have labor profit - expected >= 10%"
        
        # Print top 5 items with labor profit
        top_items = sorted(items_with_labor, key=lambda x: x['labor_profit_inr'], reverse=True)[:5]
        print(f"  Top 5 items by labor profit:")
        for item in top_items:
            print(f"    - {item['item_name']}: ₹{item['labor_profit_inr']:,.2f}")
        
        print(f"✓ {len(items_with_labor)} items have non-zero labor_profit_inr")


class TestSalesSummary:
    """Tests for GET /api/analytics/sales-summary - Total labor calculation"""
    
    def test_sales_summary_returns_200(self):
        """Verify sales-summary endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/analytics/sales-summary")
        assert response.status_code == 200
        print("✓ Sales summary endpoint returns 200")
    
    def test_sales_summary_has_required_fields(self):
        """Verify sales-summary response has required fields"""
        response = requests.get(f"{BASE_URL}/api/analytics/sales-summary")
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ['total_net_wt_kg', 'total_fine_wt_kg', 'total_labor', 'transaction_count']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        print(f"✓ Sales summary has all required fields: {required_fields}")
    
    def test_total_labor_is_nonzero(self):
        """CRITICAL: total_labor should be non-zero (expected ~₹62L)"""
        response = requests.get(f"{BASE_URL}/api/analytics/sales-summary")
        assert response.status_code == 200
        data = response.json()
        
        total_labor = data.get('total_labor', 0)
        print(f"  total_labor: ₹{total_labor:,.2f}")
        
        # Should be non-zero
        assert total_labor != 0, "total_labor is zero - BUG: Labor calculation not using total_amount"
        print(f"✓ total_labor is non-zero: ₹{total_labor:,.2f}")
    
    def test_total_labor_is_substantial(self):
        """total_labor should be substantial (expected ~₹62L)"""
        response = requests.get(f"{BASE_URL}/api/analytics/sales-summary")
        assert response.status_code == 200
        data = response.json()
        
        total_labor = data.get('total_labor', 0)
        
        # Should be at least ₹1L given the business scale
        assert abs(total_labor) >= 100000, f"total_labor seems too low: {total_labor} (expected >= ₹1L)"
        print(f"✓ total_labor is substantial: ₹{total_labor:,.2f}")


class TestCustomerProfit:
    """Tests for GET /api/analytics/customer-profit"""
    
    def test_customer_profit_returns_200(self):
        """Verify customer-profit endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/analytics/customer-profit")
        assert response.status_code == 200
        print("✓ Customer profit endpoint returns 200")
    
    def test_customer_profit_has_labor_values(self):
        """Verify customers have reasonable labour_profit_inr values"""
        response = requests.get(f"{BASE_URL}/api/analytics/customer-profit")
        assert response.status_code == 200
        data = response.json()
        
        customers = data.get('customers', [])
        assert len(customers) > 0, "No customers in profit analysis"
        
        # Check that customers have labour_profit_inr field
        customers_with_labor = [c for c in customers if 'labour_profit_inr' in c]
        assert len(customers_with_labor) > 0, "No customers have labour_profit_inr field"
        
        # Check for non-zero values
        nonzero_labor = [c for c in customers_with_labor if abs(c.get('labour_profit_inr', 0)) > 0]
        print(f"  Total customers: {len(customers)}")
        print(f"  Customers with non-zero labour_profit_inr: {len(nonzero_labor)}")
        
        # Print top 3
        if nonzero_labor:
            top = sorted(nonzero_labor, key=lambda x: x['labour_profit_inr'], reverse=True)[:3]
            print(f"  Top 3 customers by labour profit:")
            for c in top:
                print(f"    - {c['customer_name']}: ₹{c['labour_profit_inr']:,.2f}")
        
        print(f"✓ Customer profit data present with {len(nonzero_labor)} customers having labour profits")


class TestSupplierProfit:
    """Tests for GET /api/analytics/supplier-profit"""
    
    def test_supplier_profit_returns_200(self):
        """Verify supplier-profit endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/analytics/supplier-profit")
        assert response.status_code == 200
        print("✓ Supplier profit endpoint returns 200")
    
    def test_supplier_profit_has_labor_values(self):
        """Verify suppliers have labor_profit_inr values"""
        response = requests.get(f"{BASE_URL}/api/analytics/supplier-profit")
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert 'suppliers' in data or 'total_suppliers' in data, "Missing suppliers data"
        
        suppliers = data.get('suppliers', [])
        if len(suppliers) > 0:
            # Check first supplier has labor_profit_inr
            first_supplier = suppliers[0]
            assert 'labor_profit_inr' in first_supplier, "Supplier missing labor_profit_inr field"
            print(f"  First supplier: {first_supplier.get('supplier_name', 'N/A')}, labor_profit_inr: ₹{first_supplier.get('labor_profit_inr', 0):,.2f}")
        
        print(f"✓ Supplier profit data present with {len(suppliers)} suppliers")


class TestUnmappedItems:
    """Tests for GET /api/mappings/unmapped - Filtering fix"""
    
    def test_unmapped_returns_200(self):
        """Verify unmapped endpoint returns 200"""
        response = requests.get(f"{BASE_URL}/api/mappings/unmapped")
        assert response.status_code == 200
        print("✓ Unmapped items endpoint returns 200")
    
    def test_unmapped_has_required_fields(self):
        """Verify unmapped response has required fields"""
        response = requests.get(f"{BASE_URL}/api/mappings/unmapped")
        assert response.status_code == 200
        data = response.json()
        
        assert 'unmapped_items' in data, "Missing unmapped_items field"
        assert 'count' in data, "Missing count field"
        print(f"✓ Unmapped response has required fields, count: {data['count']}")
    
    def test_no_purely_numeric_items(self):
        """CRITICAL: Unmapped items should NOT contain purely numeric names like '136'"""
        response = requests.get(f"{BASE_URL}/api/mappings/unmapped")
        assert response.status_code == 200
        data = response.json()
        
        unmapped_items = data.get('unmapped_items', [])
        
        # Find any purely numeric items
        numeric_items = [item for item in unmapped_items if item.isdigit()]
        
        if numeric_items:
            print(f"  FOUND NUMERIC ITEMS (BUG): {numeric_items[:10]}")
        
        assert len(numeric_items) == 0, f"Found {len(numeric_items)} purely numeric items in unmapped: {numeric_items[:10]} - BUG NOT FIXED"
        print(f"✓ No purely numeric items in unmapped list (filtering works)")
    
    def test_no_136_in_unmapped(self):
        """CRITICAL: '136' should NOT be in unmapped items"""
        response = requests.get(f"{BASE_URL}/api/mappings/unmapped")
        assert response.status_code == 200
        data = response.json()
        
        unmapped_items = data.get('unmapped_items', [])
        
        assert '136' not in unmapped_items, "'136' is still in unmapped items - BUG NOT FIXED"
        print(f"✓ '136' is NOT in unmapped items (bug fixed)")
    
    def test_no_test_data_items(self):
        """Unmapped items should NOT contain test data patterns"""
        response = requests.get(f"{BASE_URL}/api/mappings/unmapped")
        assert response.status_code == 200
        data = response.json()
        
        unmapped_items = data.get('unmapped_items', [])
        
        # Check for test data patterns
        test_patterns = ['TEST_SILVER_ITEM_', 'Item ', 'Batch']
        test_items = []
        for item in unmapped_items:
            for pattern in test_patterns:
                if item.startswith(pattern):
                    test_items.append(item)
                    break
        
        if test_items:
            print(f"  FOUND TEST DATA ITEMS: {test_items[:10]}")
        
        assert len(test_items) == 0, f"Found test data items in unmapped: {test_items[:10]}"
        print(f"✓ No test data items in unmapped list")


class TestDateRangeFiltering:
    """Test date range filtering on profit endpoints"""
    
    def test_profit_with_date_range(self):
        """Verify profit endpoint accepts date range parameters"""
        # Use a reasonable date range (last year)
        response = requests.get(f"{BASE_URL}/api/analytics/profit?start_date=2025-01-01&end_date=2025-12-31")
        assert response.status_code == 200
        data = response.json()
        assert 'labor_profit_inr' in data
        print(f"✓ Profit endpoint works with date range, labor_profit_inr: ₹{data['labor_profit_inr']:,.2f}")
    
    def test_sales_summary_with_date_range(self):
        """Verify sales-summary endpoint accepts date range parameters"""
        response = requests.get(f"{BASE_URL}/api/analytics/sales-summary?start_date=2025-01-01&end_date=2025-12-31")
        assert response.status_code == 200
        data = response.json()
        assert 'total_labor' in data
        print(f"✓ Sales summary works with date range, total_labor: ₹{data['total_labor']:,.2f}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
