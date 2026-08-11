# Test Credentials

## Admin
- Username: `admin`
- Password: `admin123`
- NOTE (Jun 1, 2026): An idempotent `seed_admin()` runs on startup — it CREATES `admin`/`admin123` only if no admin exists, and never overwrites an existing admin's password (so a custom production password is preserved). It also reactivates an inactive admin.

## Executive (Stock Entry)
- Username: `TEST_EXEC`
- Password: `exec123`
- Existing users: SEE1, SEE2, SEE3, SEE4 (passwords set by admin on production)

## Polythene Executive
- Username: `TEST_POLY_EXEC`
- Password: `polyexec123`
- Existing users: PEE1, PEE2, PEE3, PEE4 (passwords set by admin on production)

## Manager
- Username: `SMANAGER` (password set by admin on production)

## Upload Manager (uploader role — Upload Files page only)
- Username: `TEST_UPLOADER`
- Password: `upload123`

## Sales Manager
- Username: `TEST_SM`
- Password: `sm123`
- Role: `sales_manager` — sees Sales View (/manager-sales) restricted to assigned stamps + last 2 months; has executive stock-entry powers, NO approval rights
- Preview stamp assignments: STAMP 5, STAMP 7, Unassigned (the 'Unassigned' one exists so preview data shows in the view)
