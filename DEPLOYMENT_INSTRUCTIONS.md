# Deployment Instructions for StockBud

## 🚀 Step-by-Step Deployment Guide

### Step 1: Deploy the Application
1. In Emergent UI, click the **"Deploy"** button
2. Wait 10-15 minutes for deployment to complete
3. You will receive a notification when deployment is ready

### Step 2: Fix Stamp Case Issues (ONE-TIME SETUP)

After deployment completes, you MUST run stamp normalization to fix duplicate stamps:

#### Option A: From Stamp Management Page (Recommended)
1. Go to your deployed app: https://upload-recovery-4.preview.emergentagent.com
2. Login as **admin** (username: `admin`, password: `admin123`)
3. Navigate to **Stamp Management** from the sidebar
4. Click the **"Normalize All Stamps"** button (top right, next to Save button)
5. Confirm the action
6. Wait for success message
7. Page will auto-refresh

#### Option B: From Sidebar Button
1. Login as admin
2. Look for **"Fix Stamp Cases"** button in the left sidebar (below "Undo Upload")
3. Click it and confirm
4. Wait for success message
5. Page will auto-refresh

### What This Does:
- Converts all stamps to consistent "STAMP X" format (ALL CAPS)
- Examples:
  - "Stamp 1" → "STAMP 1"
  - "stamp 1" → "STAMP 1"
  - "STamp 1" → "STAMP 1"
- Consolidates duplicate stamps into single entries
- Updates master_items, transactions, and opening_stock collections

### Expected Results After Normalization:
- ✅ No more duplicate stamps in dropdowns
- ✅ STAMP 1, STAMP 2, STAMP 3, etc. (all consistent)
- ✅ STAMP 5: Will show 53 items (not split)
- ✅ STAMP 6: Will show 24 items (includes SNT-40 PREMIUM)
- ✅ Executive Stock Entry: Correct item counts per stamp
- ✅ Physical vs Book: No duplicate stamps in dropdown

---

## 📋 Post-Deployment Verification Checklist

After deploying and normalizing stamps, verify these features:

### Core Features:
- [ ] Login works for all users (admin, manager, executives, polythene)
- [ ] Stamp Management page loads without errors
- [ ] All stamps in CAPS format (STAMP 1, STAMP 2, etc.)
- [ ] No duplicate stamps in any dropdown

### New Features:
- [ ] Purchase Rates: Shows only 3 columns (Item, Tunch %, Labour/kg)
- [ ] Profit Analysis: Date filter shows sales data correctly
- [ ] Profit Analysis: All items displayed (not just 20)
- [ ] Party Analytics → Supplier Profit: Shows silver & labour profit columns
- [ ] Stamp Management: Has "Sort by Stamp" dropdown
- [ ] Stamp Management: Has "Normalize All Stamps" button
- [ ] User Management: Has Edit button (pencil icon) for each user
- [ ] Physical vs Book: Summary cards show both gross and net weights
- [ ] Mobile: Logout button visible in mobile menu

### Admin Features:
- [ ] Admin token lasts 365 days (won't expire)
- [ ] User editing works (username, password, role, active status)
- [ ] Stamp normalization button works

---

## 🔐 User Credentials

**Admin**: 
- Username: `admin`
- Password: `admin123`

**Manager**:
- Username: `SMANAGER`
- Password: `manager123`

**Stock Entry Executives**:
- Username: `SEE1`, `SEE2`, `SEE3`, `SEE4`
- Password: `executive123`

**Polythene Entry Executives**:
- Username: `PEE1`, `PEE2`, `PEE3`, `PEE4`
- Password: `poly123`

---

## ⚠️ Important Notes

1. **Run Normalization Only Once**: After deployment, run stamp normalization once to fix duplicate stamps. No need to run it again unless you import files with inconsistent stamp cases.

2. **Cache Busting**: If you don't see changes immediately:
   - Hard refresh: **Ctrl+Shift+R** (Windows) or **Cmd+Shift+R** (Mac)
   - Clear browser cache
   - Use Incognito mode for testing

3. **Data Integrity**: The normalization is safe and only consolidates duplicate stamps. Your data will not be lost.

4. **Future Imports**: All future Excel file imports will auto-normalize stamps to CAPS format, preventing this issue.

---

## 📞 Support

If you encounter any issues after deployment:
1. Check browser console for errors (F12 → Console tab)
2. Verify backend is responding: Visit `/api/health` endpoint
3. Try logging out and logging back in
4. Clear all browser data and retry

---

## ✅ Deployment Checklist

- [ ] Step 1: Click Deploy in Emergent UI
- [ ] Step 2: Wait for deployment notification (10-15 min)
- [ ] Step 3: Hard refresh browser (Ctrl+Shift+R)
- [ ] Step 4: Login as admin
- [ ] Step 5: Go to Stamp Management
- [ ] Step 6: Click "Normalize All Stamps" button
- [ ] Step 7: Confirm and wait for success
- [ ] Step 8: Verify no duplicate stamps
- [ ] Step 9: Test all features from checklist above

---

**Once these steps are complete, your StockBud application will be fully deployed and operational!** 🚀
