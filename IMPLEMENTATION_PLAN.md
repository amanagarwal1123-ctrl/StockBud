# Implementation Plan - User Requirements

## Tasks Overview

### Task 1: Purchase Rates - Remove Total Stats
**File**: `/app/frontend/src/pages/PurchaseRates.jsx`
**Change**: Remove the 2 stat cards showing "Total Purchased" and "Total Labour"
**Lines**: 79-98 (remove the last 2 Card components)
**Status**: NOT STARTED

### Task 2: Admin Perpetual Login
**Files**: 
- `/app/backend/auth.py` - Increase token expiry for admin to 365 days
- `/app/frontend/src/context/AuthContext.jsx` - Auto-refresh token before expiry
**Change**: Admin tokens never expire, auto-refresh on activity
**Status**: NOT STARTED

### Task 3: Exclude Unmapped Items from Profit
**File**: `/app/backend/server.py`
**Function**: `calculate_profit()` line 2362
**Change**: Filter out items with stamp="Unassigned" or no stamp
**Current**: Excludes hardcoded list ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]
**New**: Also exclude items where stamp is missing or "Unassigned"
**Status**: NOT STARTED

### Task 4: Display ALL Items in Profit Analysis
**File**: `/app/backend/server.py`
**Line**: 2489 - `"top_profitable_items": item_profits[:20]`
**Change**: Return ALL items, not just top 20
**Frontend**: `/app/frontend/src/pages/ProfitAnalysis.jsx` - Add pagination
**Status**: NOT STARTED

### Task 5: Supplier-Wise Profit Calculation
**File**: `/app/backend/server.py`
**Function**: `get_supplier_profit()` line 2016
**Current Logic**: Only aggregates purchase data
**New Logic**: 
  - For each supplier, identify which items they supply
  - Calculate profit per item (silver + labour)
  - Multiply by weight purchased from that supplier
  - Sum across all items for total supplier profit
**Status**: NOT STARTED

### Task 6: Deleted Mappings Reappear as Unmapped
**File**: `/app/backend/server.py`
**Function**: `get_unmapped_items()` line 2082
**Current**: Checks if name is in mappings collection
**Issue**: When mapping is deleted, it's still excluded from unmapped
**Fix**: The logic is already correct - when mapping is deleted, it's removed from `mapped_names` set
**Verify**: Check if delete endpoint is working correctly
**Status**: NEEDS INVESTIGATION

### Task 7: Stamp Management - Sort by Stamp
**File**: `/app/frontend/src/pages/StampManagement.jsx`
**Change**: Add sort dropdown to sort items by stamp number
**Status**: NOT STARTED

### Task 8: Verify Profit Calculation Logic
**Action**: Review the formulas in `calculate_profit()` function
**Current Formula**:
  - Silver Profit (kg) = (sale_tunch - purchase_tunch) * sale_net_weight / 100
  - Labour Profit (₹) = (sale_labour_per_gram - purchase_labour_per_gram) * sale_net_weight
**Status**: NEEDS REVIEW WITH USER

## Implementation Order

1. Task 1 (Quick) - Remove stats from Purchase Rates
2. Task 3 (Quick) - Exclude unmapped from profit
3. Task 4 (Medium) - Display all items in profit
4. Task 7 (Quick) - Add sort to Stamp Management
5. Task 6 (Investigation) - Verify mapping deletion
6. Task 5 (Complex) - Implement supplier profit logic
7. Task 2 (Medium) - Perpetual admin login
8. Task 8 (Review) - Verify profit formulas with user
