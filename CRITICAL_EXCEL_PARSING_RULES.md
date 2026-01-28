# CRITICAL EXCEL PARSING RULES

## ⚠️ ALWAYS SKIP "TOTALS" ROW IN ALL EXCEL FILES

**Rule:** When parsing ANY Excel file, ALWAYS check if the item name contains "total" (case-insensitive) and SKIP IT.

**Why:** Excel files have a "Totals" row at the bottom which is a SUM of all entries. Including this row causes:
- Double-counting in calculations
- Incorrect inventory totals
- Massive profit calculation errors

**Apply to ALL file types:**
- ✅ Purchase files (PURCH_TEST.xlsx)
- ✅ Sale files (SALE_TEST.xlsx)
- ✅ Opening Stock (PREV_STOCK.xlsx)
- ✅ Physical Stock (CURRENT_STOCK.xlsx)
- ✅ Master Stock (STOCK 2026.xlsx)
- ✅ Purchase Cumulative (PURCHASE_CUMUL.xlsx)

**Code Pattern:**
```python
# After reading item_name/particular column
if 'total' in item_name.lower():
    continue  # SKIP THIS ROW!
```

**Locations in code:**
- `/app/backend/server.py` - `parse_excel_file()` function
- All upload endpoints (opening-stock, master-stock, purchase-ledger, etc.)

**Historical Issues:**
- Issue #1: Opening stock showed wrong total (included Totals row)
- Issue #2: Purchase ledger showed 1 extra item (Totals row with huge values)
- Issue #3: Inventory calculation was off

**Prevention:**
- Every Excel parser MUST have the totals check
- Review all upload endpoints regularly
- Test with actual files that have Totals rows
