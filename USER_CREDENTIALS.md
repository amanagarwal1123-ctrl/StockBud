# StockBud - User Credentials

## ✅ All Logins Working (Verified via API)

All user passwords have been reset and verified. Backend authentication is working correctly.

---

## 🔑 Login Credentials

### **Admin Users**
- **Username**: `admin`  
  **Password**: `admin123`  
  **Role**: System Administrator  
  **Access**: Full system access, all features

- **Username**: `admin2`  
  **Password**: `admin123`  
  **Role**: Admin  
  **Access**: Full system access

---

### **Manager**
- **Username**: `SMANAGER`  
  **Password**: `manager123`  
  **Role**: Manager  
  **Access**: Approve/reject stock entries, view reports, manage notifications
  **Default Page**: Physical vs Book comparison

---

### **Stock Entry Executives (SEE)**
Enter physical stock counts for specific stamps.

- **Username**: `SEE1`  
  **Password**: `executive123`  
  **Default Page**: Stock Entry

- **Username**: `SEE2`  
  **Password**: `executive123`  

- **Username**: `SEE3`  
  **Password**: `executive123`  

- **Username**: `SEE4`  
  **Password**: `executive123`  

---

### **Polythene Entry Executives (PEE)**
Add/subtract polythene weight from items.

- **Username**: `PEE1`  
  **Password**: `poly123`  
  **Default Page**: Polythene Entry

- **Username**: `PEE2`  
  **Password**: `poly123`  

- **Username**: `PEE3`  
  **Password**: `poly123`  

- **Username**: `PEE4`  
  **Password**: `poly123`  

- **Username**: `poly_exec`  
  **Password**: `poly123`  

---

## ✅ Testing Status

**Backend API**: ✅ All logins tested and working  
**Date**: 2026-02-05  

### Verification Commands Used:
```bash
# Test admin login
curl -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Test SEE1 login
curl -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"SEE1","password":"executive123"}'

# Test Manager login
curl -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"SMANAGER","password":"manager123"}'

# Test PEE1 login
curl -X POST "$API_URL/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"PEE1","password":"poly123"}'
```

All tests returned successful JWT tokens.

---

## 🔧 Password Reset History

**Last Reset**: 2026-02-05 12:16 UTC  
**Reason**: Fixed authentication issues after system updates  
**Method**: Direct database password hash updates using bcrypt  
**Status**: All 12 users successfully reset  

---

## 📝 Notes

1. **Login Endpoint**: `/api/auth/login` (POST)
2. **Token Expiry**: 18 hours
3. **Password Format**: All passwords use standard alphanumeric format
4. **Role-Based Access**: Each role automatically redirects to their appropriate default page
5. **Frontend Login**: Use the credentials above at http://localhost:3000

---

## 🔒 Security Notes

- All passwords are hashed using bcrypt
- JWT tokens are required for authenticated API calls
- Tokens must be included in Authorization header: `Bearer <token>`
- Change default passwords in production environment

---

## ⚠️ Troubleshooting

If login fails in the frontend but API tests work:
1. Clear browser cache and cookies
2. Check browser console for errors
3. Verify REACT_APP_BACKEND_URL in frontend/.env
4. Ensure backend service is running: `sudo supervisorctl status backend`

If you need to reset a password manually, contact system administrator.
