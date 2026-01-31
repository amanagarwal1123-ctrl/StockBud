from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query, Query, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import pandas as pd
import openpyxl
from io import BytesIO
import json
from collections import defaultdict
import jwt
from passlib.context import CryptContext

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Authentication setup
SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'stockbud-secret-key-change-in-production')
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 18

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()


# Health check endpoint for Kubernetes
@app.get("/health")
async def health_check():
    """Health check endpoint for deployment"""
    return {"status": "healthy", "service": "stockbud-backend"}

@app.get("/api/health")
async def api_health_check():
    """Health check endpoint under /api prefix"""
    return {"status": "healthy", "service": "stockbud-backend"}


api_router = APIRouter(prefix="/api")

# Models
class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    batch_id: Optional[str] = None  # Track which upload this transaction belongs to
    date: Optional[str] = None
    type: str  # 'purchase', 'purchase_return', 'sale', 'sale_return'
    refno: Optional[str] = None
    party_name: Optional[str] = None
    item_name: str
    stamp: Optional[str] = None
    tag_no: Optional[str] = None
    gr_wt: float = 0.0
    net_wt: float = 0.0  # Gold Std. for sales
    fine: float = 0.0  # Sil.Fine
    labor: float = 0.0  # Total/Lbr
    labor_on: Optional[str] = None  # 'Wt' or 'Pc'
    dia_wt: float = 0.0
    stn_wt: float = 0.0
    tunch: Optional[str] = None
    rate: float = 0.0
    total_pc: int = 0
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    # Financial fields for profit calculation
    total_amount: float = 0.0
    taxable_value: float = 0.0

class OpeningStock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: Optional[str] = None
    unit: Optional[str] = None
    pc: int = 0
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine: float = 0.0
    labor_wt: float = 0.0
    labor_rs: float = 0.0
    rate: float = 0.0
    total: float = 0.0
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PhysicalStock(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: Optional[str] = None
    pc: int = 0
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine: float = 0.0
    verification_date: Optional[str] = None
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class MasterItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: str
    gr_wt: float = 0.0
    net_wt: float = 0.0
    is_master: bool = True
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ItemMapping(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_name: str  # Name found in purchase/sale files
    master_name: str  # Name in STOCK 2026
    created_by: str = "system"
    created_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PurchaseLedger(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    purchase_tunch: float
    labour_per_kg: float
    total_purchased_kg: float
    total_fine_kg: float
    total_labour: float
    last_updated: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    password_hash: str
    full_name: str
    role: str  # 'admin', 'manager', 'executive'
    is_active: bool = True
    created_by: str = "system"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class LoginRequest(BaseModel):
    username: str
    password: str


# Authentication Helper Functions
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return current user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid authentication")
        
        user = await db.users.find_one({"username": username}, {"_id": 0, "password_hash": 0})
        if user is None or not user.get('is_active'):
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired - please login again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def require_role(required_roles: List[str], user: dict = Depends(get_current_user)) -> dict:
    """Check if user has required role"""
    if user.get('role') not in required_roles:
        raise HTTPException(status_code=403, detail=f"Access denied. Required role: {', '.join(required_roles)}")
    return user

class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class ActionHistory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_type: str  # 'upload_purchase', 'upload_sale', 'upload_stock', 'assign_stamp', 'resolve_negative'
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    description: str
    data_snapshot: Dict[str, Any] = {}
    can_undo: bool = True

class ResetRequest(BaseModel):
    password: str

# Helper Functions
def get_column_value(row, possible_names, default=''):
    """Try multiple column name variations"""
    for name in possible_names:
        if name in row.index and pd.notna(row.get(name)):
            val = row.get(name)
            if val != '' and str(val).strip() != '':
                return val
    return default

def parse_labor_value(tag_no):
    """Extract labor value and type from Tag.No. like '13 Wt' or '17 Pc'"""
    if not tag_no or pd.isna(tag_no):
        return 0.0, None
    tag_str = str(tag_no).strip().upper()
    parts = tag_str.split()
    if len(parts) >= 2:
        try:
            value = float(parts[0])
            labor_type = parts[1] if parts[1] in ['WT', 'PC'] else None
            return value, labor_type
        except:
            pass
    return 0.0, None

def parse_excel_file(file_content: bytes, file_type: str) -> List[Dict]:
    """Parse Excel file and return list of rows. Excel files have weights in KG, multiply by 1000 to store as grams."""
    try:
        df = pd.read_excel(BytesIO(file_content), header=None)
        
        # Find the actual header row
        header_row_idx = None
        for idx, row in df.iterrows():
            row_str = ' '.join(str(val).lower() for val in row if pd.notna(val))
            if 'item name' in row_str or 'particular' in row_str or 'party name' in row_str:
                header_row_idx = idx
                break
        
        if header_row_idx is None:
            df = pd.read_excel(BytesIO(file_content))
        else:
            df = pd.read_excel(BytesIO(file_content), header=header_row_idx)
        
        df = df.fillna('')
        df.columns = df.columns.str.strip()
        
        # IMPORTANT: Excel files have weights in KG, multiply by 1000 to store as grams internally
        KG_TO_GRAMS = 1000
        
        if file_type == 'purchase':
            records = []
            for _, row in df.iterrows():
                try:
                    item_name = str(get_column_value(row, ['Item Name', 'Particular', 'item name'], ''))
                    if not item_name or len(item_name) < 2:
                        continue
                    
                    trans_type = str(get_column_value(row, ['Type', 'type'], 'P')).strip().upper()
                    
                    # Skip Totals row (Type is a number like '333')
                    if trans_type.isdigit():
                        continue
                    
                    tag_no = str(get_column_value(row, ['Tag.No.', 'Tag No', 'tag no'], ''))
                    labor_val, labor_on = parse_labor_value(tag_no)
                    
                    # Read labour from Wt/Rs column
                    wt_rs_value = get_column_value(row, ['Wt/Rs', 'Wt Rs'], '')
                    if wt_rs_value:
                        labor_val = float(wt_rs_value) if str(wt_rs_value).replace('.', '').isdigit() else labor_val
                    
                    # Labour is in "Total" column (total labour cost for the transaction)
                    total_labor = float(get_column_value(row, ['Total', 'total'], 0) or 0)
                    
                    # Calculate purchase tunch = tunch + wstg
                    tunch_val = float(get_column_value(row, ['Tunch', 'tunch'], 0) or 0)
                    wstg_val = float(get_column_value(row, ['Wstg', 'wstg'], 0) or 0)
                    purchase_tunch = tunch_val + wstg_val if not pd.isna(tunch_val) and not pd.isna(wstg_val) else (tunch_val if not pd.isna(tunch_val) else 0)
                    
                    # Store type as-is; weights are already positive/negative in Excel
                    record = {
                        'date': str(get_column_value(row, ['Date', 'date'], '')),
                        'type': 'purchase' if trans_type in ['P', 'PURCHASE'] else 'purchase_return',
                        'refno': str(get_column_value(row, ['Refno', 'refno', 'Ref No'], '')),
                        'party_name': str(get_column_value(row, ['Party Name', 'party name', 'Party'], '')),
                        'item_name': item_name,
                        'stamp': str(get_column_value(row, ['Stamp', 'stamp'], '')),
                        'tag_no': tag_no,
                        'gr_wt': float(get_column_value(row, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'], 0) or 0) * KG_TO_GRAMS,
                        'net_wt': float(get_column_value(row, ['Net.Wt.', 'Net Wt'], 0) or 0) * KG_TO_GRAMS,
                        'fine': float(get_column_value(row, ['Fine', 'Sil.Fine', 'Sil Fine', 'Silver Fine'], 0) or 0) * KG_TO_GRAMS,
                        'labor': total_labor,
                        'labor_on': labor_on,
                        'dia_wt': float(get_column_value(row, ['Dia.Wt.', 'Dia Wt'], 0) or 0) * KG_TO_GRAMS,
                        'stn_wt': float(get_column_value(row, ['Stn.Wt.', 'Stn Wt'], 0) or 0) * KG_TO_GRAMS,
                        'tunch': str(purchase_tunch),
                        'rate': float(get_column_value(row, ['Rate', 'rate'], 0) or 0),
                        'total_pc': int(get_column_value(row, ['Pc', 'pc', 'Pieces'], 0) or 0),
                        'total_amount': float(get_column_value(row, ['Total', 'total'], 0) or 0)
                    }
                    records.append(record)
                except Exception as e:
                    continue
            return records
            
        elif file_type == 'sale':
            records = []
            for _, row in df.iterrows():
                try:
                    item_name = str(get_column_value(row, ['Item Name', 'Particular', 'item name'], ''))
                    if not item_name or len(item_name) < 2:
                        continue
                    
                    trans_type = str(get_column_value(row, ['Type', 'type'], 'S')).strip().upper()
                    
                    # Skip Totals row (Type is a number like '8085')
                    if trans_type.isdigit():
                        continue
                    
                    tag_no = str(get_column_value(row, ['Lbr. On Tag.No.', 'Tag.No.', 'Tag No'], ''))
                    labor_val, labor_on = parse_labor_value(tag_no)
                    
                    # Read labour from On column (might have values like "100", "1200", etc.)
                    on_value = get_column_value(row, ['On', 'on'], '')
                    if on_value and str(on_value).replace('.', '').isdigit():
                        labor_val = float(on_value)
                    
                    # Labour is in "Total" column (total labour cost for the transaction)
                    total_labor = float(get_column_value(row, ['Total', 'total'], 0) or 0)
                    
                    # Sale tunch is just the tunch column (no wstg)
                    sale_tunch = float(get_column_value(row, ['Tunch', 'tunch'], 0) or 0)
                    
                    # Store type as-is; weights are already positive/negative in Excel
                    record = {
                        'type': 'sale' if trans_type in ['S', 'SALE'] else 'sale_return',
                        'date': str(get_column_value(row, ['Date', 'date'], '')),
                        'refno': str(get_column_value(row, ['Refno', 'refno', 'Ref No'], '')),
                        'party_name': str(get_column_value(row, ['Party Name', 'party name', 'Party'], '')),
                        'item_name': item_name,
                        'stamp': str(get_column_value(row, ['Stamp', 'stamp'], '')),
                        'tag_no': tag_no,
                        'gr_wt': float(get_column_value(row, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'], 0) or 0) * KG_TO_GRAMS,
                        'net_wt': float(get_column_value(row, ['Gold Std.', 'Net.Wt.', 'Net Wt'], 0) or 0) * KG_TO_GRAMS,
                        'fine': float(get_column_value(row, ['Fine', 'Sil.Fine', 'Sil Fine'], 0) or 0) * KG_TO_GRAMS,
                        'labor': total_labor,
                        'labor_on': labor_on,
                        'dia_wt': float(get_column_value(row, ['Dia.Wt.', 'Dia Wt'], 0) or 0) * KG_TO_GRAMS,
                        'stn_wt': float(get_column_value(row, ['Stn.Wt.', 'Stn Wt'], 0) or 0) * KG_TO_GRAMS,
                        'tunch': str(sale_tunch),
                        'total_amount': float(get_column_value(row, ['Total', 'total'], 0) or 0),
                        'taxable_value': float(get_column_value(row, ['Taxable Val.', 'Taxable Value'], 0) or 0),
                        'total_pc': int(get_column_value(row, ['Pc', 'pc'], 0) or 0)
                    }
                    records.append(record)
                except Exception as e:
                    continue
            return records
            
        elif file_type == 'opening_stock':
            records = []
            for _, row in df.iterrows():
                try:
                    item_name = str(get_column_value(row, ['Item Name', 'Particular', 'item name', 'Stock'], ''))
                    if not item_name or len(item_name) < 2:
                        continue
                    
                    # Skip the "Totals" row - user clarified we should sum individual entries
                    if 'total' in item_name.lower():
                        continue
                    
                    # Handle "Gold Std." as Net Weight in stock files
                    net_wt_value = get_column_value(row, ['Gold Std.', 'Net.Wt.', 'Net Wt'], 0)
                    
                    # Labour is in "Total" column
                    total_labor = float(get_column_value(row, ['Total', 'total'], 0) or 0)
                    
                    # Calculate stock tunch = tunch + wstg
                    tunch_val = float(get_column_value(row, ['Tunch', 'tunch'], 0) or 0)
                    wstg_val = float(get_column_value(row, ['Wstg', 'wstg'], 0) or 0)
                    stock_tunch = tunch_val + wstg_val if not pd.isna(tunch_val) and not pd.isna(wstg_val) else (tunch_val if not pd.isna(tunch_val) else 0)
                    
                    record = {
                        'item_name': item_name,
                        'stamp': str(get_column_value(row, ['Stamp', 'stamp'], '')),
                        'unit': str(get_column_value(row, ['Unit', 'unit'], '')),
                        'pc': int(get_column_value(row, ['Pc', 'pc', 'Pieces'], 0) or 0),
                        'gr_wt': float(get_column_value(row, ['Gr.Wt.', 'Gr Wt', 'Gross Wt'], 0) or 0) * KG_TO_GRAMS,
                        'net_wt': float(net_wt_value or 0) * KG_TO_GRAMS,
                        'fine': float(get_column_value(row, ['Sil.Fine', 'Fine', 'fine'], 0) or 0) * KG_TO_GRAMS,
                        'labor_wt': 0.0,
                        'labor_rs': 0.0,
                        'rate': float(get_column_value(row, ['Rate', 'rate'], 0) or 0),
                        'total': total_labor
                    }
                    records.append(record)
                except Exception as e:
                    continue
            return records
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing Excel file: {str(e)}")

# Save action for undo/redo and accountability
async def save_action(action_type: str, description: str, data_snapshot: dict = None, user: dict = None):
    action = ActionHistory(
        action_type=action_type,
        description=description,
        data_snapshot=data_snapshot or {}
    )
    await db.action_history.insert_one(action.model_dump())
    
    # Also log to activity_log for accountability if user provided
    if user:
        await db.activity_log.insert_one({
            'user': user.get('username', 'system'),
            'user_role': user.get('role', 'system'),
            'action_type': action_type,
            'description': description,
            'details': data_snapshot or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    # Keep only last 20 actions
    count = await db.action_history.count_documents({})
    if count > 20:
        oldest = await db.action_history.find({}, {"_id": 1}).sort("timestamp", 1).limit(count - 20).to_list(count)
        if oldest:
            await db.action_history.delete_many({"_id": {"$in": [doc["_id"] for doc in oldest]}})

@api_router.post("/opening-stock/upload")
async def upload_opening_stock(file: UploadFile = File(...)):
    """Upload opening stock - Parse and MERGE items by name (sum weights regardless of stamp)"""
    content = await file.read()
    
    try:
        # Parse individual items using the standard parser
        records = parse_excel_file(content, 'opening_stock')
        
        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in file")
        
        # MERGE items by name - sum all weights for same item
        merged_items = {}
        for record in records:
            key = record['item_name'].strip().lower()
            if key not in merged_items:
                merged_items[key] = {
                    'item_name': record['item_name'],
                    'stamp': record.get('stamp', ''),
                    'unit': record.get('unit', ''),
                    'pc': 0,
                    'gr_wt': 0.0,
                    'net_wt': 0.0,
                    'fine': 0.0,
                    'labor_wt': record.get('labor_wt', 0.0),
                    'labor_rs': record.get('labor_rs', 0.0),
                    'rate': record.get('rate', 0.0),
                    'total': 0.0
                }
            
            # Sum weights (including negative values)
            merged_items[key]['gr_wt'] += record.get('gr_wt', 0)
            merged_items[key]['net_wt'] += record.get('net_wt', 0)
            merged_items[key]['fine'] += record.get('fine', 0)
            merged_items[key]['pc'] += record.get('pc', 0)
            merged_items[key]['total'] += record.get('total', 0)
            
            # Keep stamp if this entry has one
            if record.get('stamp') and not merged_items[key]['stamp']:
                merged_items[key]['stamp'] = record['stamp']
        
        # Clear existing opening stock
        await db.opening_stock.delete_many({})
        
        # Insert merged items
        stock_items = [OpeningStock(**item).model_dump() for item in merged_items.values()]
        await db.opening_stock.insert_many(stock_items)
        
        # Calculate totals for response
        total_net_wt = sum(item['net_wt'] for item in stock_items)
        total_gr_wt = sum(item['gr_wt'] for item in stock_items)
        
        await save_action('upload_opening_stock', f"Uploaded {len(stock_items)} merged opening stock items, total: {total_net_wt/1000:.3f} kg")
        
        return {
            "success": True,
            "count": len(stock_items),
            "original_rows": len(records),
            "merged_items": len(stock_items),
            "total_net_wt_kg": round(total_net_wt/1000, 3),
            "total_gr_wt_kg": round(total_gr_wt/1000, 3),
            "message": f"Merged {len(records)} rows into {len(stock_items)} items. Total: {total_net_wt/1000:.3f} kg"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")


# ==================== AUTHENTICATION ENDPOINTS ====================

@api_router.post("/auth/login", response_model=Token)
async def login(request: LoginRequest):
    """Login endpoint - Returns JWT token valid for 18 hours"""
    user = await db.users.find_one({"username": request.username})
    
    if not user or not verify_password(request.password, user['password_hash']):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    if not user.get('is_active', True):
        raise HTTPException(status_code=401, detail="User account is inactive")
    
    # Create JWT token
    access_token = create_access_token({"sub": user['username'], "role": user['role']})
    
    # Remove sensitive data
    user_data = {k: v for k, v in user.items() if k not in ['_id', 'password_hash']}
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user_data
    }

@api_router.get("/auth/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current logged-in user info"""
    return current_user

@api_router.post("/auth/logout")
async def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Logged out successfully"}

# ==================== USER MANAGEMENT (Admin Only) ====================

@api_router.post("/users/create")
async def create_user(
    request: CreateUserRequest,
    current_user: dict = Depends(get_current_user)
):
    """Create new user (Admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can create users")
    
    # Check if username exists
    existing = await db.users.find_one({"username": request.username})
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    
    # Validate role
    if request.role not in ['admin', 'manager', 'executive', 'polythene_executive']:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    # Create user
    user = User(
        username=request.username,
        password_hash=get_password_hash(request.password),
        full_name=request.full_name,
        role=request.role,
        created_by=current_user['username']
    )
    
    await db.users.insert_one(user.model_dump())
    
    return {
        "success": True,
        "message": f"User {request.username} created successfully",
        "user": {
            "username": user.username,
            "full_name": user.full_name,
            "role": user.role
        }
    }

@api_router.get("/users/list")
async def list_users(current_user: dict = Depends(get_current_user)):
    """List all users (Admin and Manager can view)"""
    if current_user['role'] not in ['admin', 'manager']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
    return users

@api_router.delete("/users/{username}")
async def delete_user(
    username: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete user (Admin only)"""
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Only admins can delete users")
    
    if username == current_user['username']:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    
    result = await db.users.delete_one({"username": username})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"success": True, "message": f"User {username} deleted"}

@api_router.post("/users/initialize-admin")
async def initialize_admin():
    """Create initial admin user if no users exist (one-time setup)"""
    count = await db.users.count_documents({})
    
    if count > 0:
        raise HTTPException(status_code=400, detail="Users already exist. Use login.")
    
    # Create default admin
    admin = User(
        username="admin",
        password_hash=get_password_hash("admin123"),  # Change on first login!
        full_name="System Administrator",
        role="admin",
        created_by="system"
    )
    
    await db.users.insert_one(admin.model_dump())
    
    return {
        "success": True,
        "message": "Admin user created",
        "username": "admin",
        "password": "admin123",
        "warning": "Please change password after first login!"
    }

@api_router.post("/transactions/upload/{file_type}")
async def upload_transaction_file(
    file_type: str, 
    file: UploadFile = File(...),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Upload purchase or sale Excel file - REPLACES transactions in specified date range"""
    if file_type not in ['purchase', 'sale']:
        raise HTTPException(status_code=400, detail="file_type must be 'purchase' or 'sale'")
    
    content = await file.read()
    records = parse_excel_file(content, file_type)
    
    if not records:
        raise HTTPException(status_code=400, detail="No valid records found in file")
    
    # Generate unique batch ID for this upload
    batch_id = str(uuid.uuid4())
    
    # If date range provided, DELETE existing transactions in that range
    deleted_count = 0
    if start_date and end_date:
        delete_query = {
            "type": {"$in": [file_type, f"{file_type}_return"]},
            "date": {"$gte": start_date, "$lte": end_date}
        }
        delete_result = await db.transactions.delete_many(delete_query)
        deleted_count = delete_result.deleted_count
    
    # Add batch_id to all transactions
    for record in records:
        record['batch_id'] = batch_id
    
    # Insert new transactions
    transactions = [Transaction(**record).model_dump() for record in records]
    result = await db.transactions.insert_many(transactions)
    
    message = f"Uploaded {len(transactions)} {file_type} records"
    if deleted_count > 0:
        message += f" (replaced {deleted_count} existing records from {start_date} to {end_date})"
    
    # Save action with batch_id
    await save_action(
        f'upload_{file_type}',
        message,
        {
            'batch_id': batch_id,
            'file_name': file.filename,
            'file_type': file_type,
            'count': len(transactions),
            'start_date': start_date,
            'end_date': end_date
        }
    )
    
    return {
        "success": True,
        "count": len(transactions),
        "replaced_count": deleted_count,
        "batch_id": batch_id,
        "message": message
    }

@api_router.get("/executive/my-entries/{username}")
async def get_executive_entries(username: str, current_user: dict = Depends(get_current_user)):
    """Get all stock entries by an executive (for editing rejected ones)"""
    entries = await db.stock_entries.find(
        {'entered_by': username},
        {"_id": 0}
    ).sort('entry_date', -1).to_list(100)
    return entries

@api_router.put("/executive/update-entry/{stamp}")
async def update_stock_entry(
    stamp: str,
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Update a rejected stock entry"""
    entries = request.get('entries', [])
    
    # Update existing entry
    await db.stock_entries.update_one(
        {'stamp': stamp, 'entered_by': current_user['username'], 'status': {'$in': ['pending', 'rejected']}},
        {'$set': {
            'entries': entries,
            'entry_date': datetime.now(timezone.utc).isoformat(),
            'status': 'pending'
        }}
    )
    
    return {'success': True, 'message': 'Entry updated'}

@api_router.get("/manager/all-entries")
async def get_all_entries(current_user: dict = Depends(get_current_user)):
    """Get all stock entries for manager (pending, approved, rejected)"""
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = await db.stock_entries.find({}, {"_id": 0}).sort('entry_date', -1).to_list(200)
    return entries

@api_router.delete("/executive/delete-entry/{stamp}/{username}")
async def delete_executive_entry(stamp: str, username: str, current_user: dict = Depends(get_current_user)):
    """Delete a stock entry"""
    if current_user['username'] != username and current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Can only delete your own entries")
    
    result = await db.stock_entries.delete_one({'stamp': stamp, 'entered_by': username})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {'success': True, 'message': 'Entry deleted'}

# ==================== EXECUTIVE ENDPOINTS ====================

@api_router.post("/executive/stock-entry")
async def save_executive_stock_entry(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Save stock entry from executive (for manager approval)"""
    
    if current_user['role'] not in ['executive', 'manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    stamp = request.get('stamp')
    entries = request.get('entries', [])
    entered_by = request.get('entered_by')
    
    # Check if stamp is already approved
    approval = await db.stamp_approvals.find_one({"stamp": stamp, "is_approved": True})
    if approval:
        raise HTTPException(status_code=400, detail=f"{stamp} is already approved. Cannot modify.")
    
    # Save stock entry
    entry_record = {
        'stamp': stamp,
        'entries': entries,
        'entered_by': entered_by,
        'entry_date': datetime.now(timezone.utc).isoformat(),
        'status': 'pending',
        'approved_by': None,
        'approved_at': None,
        'iteration': 1  # Track how many times resubmitted
    }
    
    # Check if entry exists (resubmission)
    existing = await db.stock_entries.find_one({'stamp': stamp, 'entered_by': entered_by})
    if existing:
        entry_record['iteration'] = existing.get('iteration', 1) + 1


@api_router.get("/manager/approval-details/{stamp}")
async def get_approval_details(stamp: str, current_user: dict = Depends(get_current_user)):
    """Get detailed approval data including book stock for comparison"""
    
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get pending entry
    entry = await db.stock_entries.find_one({'stamp': stamp, 'status': 'pending'}, {"_id": 0})
    
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    # Get book stock breakdown for this stamp
    breakdown = await get_stamp_breakdown(stamp)
    
    # Get all stamp items from master
    master_items = await db.master_items.find({'stamp': stamp}, {"_id": 0}).to_list(1000)
    
    # Calculate book gross for each item
    book_items = {}
    for item in master_items:
        book_items[item['item_name']] = {
            'book_gross': item.get('gr_wt', 0),
            'book_net': item.get('net_wt', 0)
        }
    
    # Merge with entered data
    comparison = []
    for entered in entry.get('entries', []):
        item_name = entered['item_name']
        book_data = book_items.get(item_name, {'book_gross': 0, 'book_net': 0})
        
        comparison.append({
            'item_name': item_name,
            'entered_gross': entered['gross_wt'],
            'book_gross': book_data['book_gross'] / 1000,  # Convert to kg
            'difference': (entered['gross_wt'] - book_data['book_gross'] / 1000)
        })
    
    return {
        'entry': entry,
        'breakdown': breakdown,
        'comparison': comparison
    }


    
    # Update or insert
    await db.stock_entries.update_one(
        {'stamp': stamp, 'entered_by': entered_by},
        {'$set': entry_record},
        upsert=True
    )
    
    # Create notification for manager
    await db.notifications.insert_one({
        'type': 'stock_entry',
        'message': f'{entered_by} submitted stock for {stamp}',
        'severity': 'info',
        'for_role': 'manager',
        'stamp': stamp,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'read': False
    })
    
    # Save to history
    await save_action('stock_entry', f'{entered_by} entered stock for {stamp}', {'stamp': stamp, 'items': len(entries)})
    
    return {'success': True, 'message': f'Stock entry saved for {stamp}'}

# ==================== MANAGER ENDPOINTS ====================

@api_router.get("/manager/pending-approvals")
async def get_pending_approvals(current_user: dict = Depends(get_current_user)):
    """Get all pending stock entries for manager approval"""
    
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = await db.stock_entries.find({'status': 'pending'}, {"_id": 0}).to_list(100)
    return entries

@api_router.post("/manager/approve-stamp")
async def approve_stamp(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject a stamp's stock entry"""
    
    if current_user['role'] not in ['manager', 'admin']:
        raise HTTPException(status_code=403, detail="Only managers can approve")
    
    stamp = request.get('stamp')
    approve = request.get('approve')
    total_difference = request.get('total_difference', 0)
    
    # Get the entry
    entry = await db.stock_entries.find_one({'stamp': stamp, 'status': 'pending'})
    
    iteration = entry.get('iteration', 1) if entry else 1
    
    # Update stock entry status
    await db.stock_entries.update_many(
        {'stamp': stamp, 'status': 'pending'},
        {'$set': {
            'status': 'approved' if approve else 'rejected',
            'approved_by': current_user['username'],
            'approved_at': datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # If approved, lock the stamp
    if approve:
        await db.stamp_approvals.update_one(
            {'stamp': stamp},
            {'$set': {
                'stamp': stamp,
                'is_approved': True,
                'approved_by': current_user['username'],
                'approved_at': datetime.now(timezone.utc).isoformat(),
                'iterations': iteration,
                'total_difference': total_difference
            }},
            upsert=True
        )
        
        # Notify admin with details
        is_matching = abs(total_difference) <= 50
        await db.notifications.insert_one({
            'type': 'stamp_approval',
            'message': f'{current_user["username"]} approved {stamp} - {"✓ MATCHING" if is_matching else "⚠️ NOT MATCHING"}',
            'severity': 'success' if is_matching else 'warning',
            'for_role': 'admin',
            'stamp': stamp,
            'details': {
                'approved_by': current_user['username'],
                'iterations': iteration,
                'total_difference_grams': total_difference,
                'is_matching': is_matching,
                'entered_by': entry.get('entered_by') if entry else 'unknown'
            },
            'created_at': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    
    return {'success': True, 'message': f'{stamp} {"approved" if approve else "rejected"}', 'iterations': iteration}

@api_router.get("/notifications/my")
async def get_my_notifications(current_user: dict = Depends(get_current_user)):
    """Get notifications for current user's role"""
    
    notifications = await db.notifications.find(
        {'for_role': {'$in': [current_user['role'], 'all']}},
        {"_id": 0}
    ).sort('created_at', -1).limit(50).to_list(50)
    
    return notifications

@api_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark notification as read"""
    await db.notifications.update_one(
        {'id': notification_id},
        {'$set': {'read': True}}
    )


# ==================== POLYTHENE EXECUTIVE ENDPOINTS ====================

@api_router.post("/polythene/adjust")
async def adjust_polythene(
    item_name: str,
    poly_weight: float,
    operation: str,
    adjusted_by: str,
    current_user: dict = Depends(get_current_user)
):
    """Adjust polythene weight for an item (gross weight changes, net stays same)"""
    
    if current_user['role'] not in ['polythene_executive', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Save polythene adjustment
    adjustment = {
        'id': str(uuid.uuid4()),
        'item_name': item_name,
        'poly_weight': poly_weight,
        'operation': operation,
        'adjusted_by': adjusted_by,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'date': datetime.now(timezone.utc).date().isoformat()
    }
    
    await db.polythene_adjustments.insert_one(adjustment)
    
    await db.activity_log.insert_one({
        'user': adjusted_by,
        'user_role': current_user['role'],
        'action_type': 'polythene_adjustment',
        'description': f'{operation.upper()} {poly_weight} kg polythene for {item_name}',
        'details': {'item': item_name, 'weight': poly_weight, 'operation': operation},
        'timestamp': datetime.now(timezone.utc).isoformat()
    })
    
    return {'success': True, 'message': 'Polythene adjustment saved'}

@api_router.post("/polythene/adjust-batch")
async def adjust_polythene_batch(
    request: Dict,
    current_user: dict = Depends(get_current_user)
):
    """Save multiple polythene adjustments at once"""
    
    if current_user['role'] not in ['polythene_executive', 'admin']:
        raise HTTPException(status_code=403, detail="Access denied")
    
    entries = request.get('entries', [])
    adjusted_by = request.get('adjusted_by')
    
    saved_entries = []
    
    for entry in entries:
        adjustment = {
            'id': str(uuid.uuid4()),
            'item_name': entry['item_name'],
            'stamp': entry.get('stamp', ''),
            'poly_weight': entry['poly_weight'],
            'operation': entry['operation'],
            'adjusted_by': adjusted_by,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'date': datetime.now(timezone.utc).date().isoformat()
        }
        
        saved_entries.append(adjustment)
        
        # Log activity
        await db.activity_log.insert_one({
            'user': adjusted_by,
            'user_role': current_user['role'],
            'action_type': 'polythene_adjustment',
            'description': f'{entry["operation"].upper()} {entry["poly_weight"]} kg polythene for {entry["item_name"]}',
            'details': entry,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
    
    # Insert all at once
    if saved_entries:
        await db.polythene_adjustments.insert_many(saved_entries)
    
    return {'success': True, 'message': f'{len(saved_entries)} polythene adjustments saved', 'count': len(saved_entries)}

@api_router.get("/polythene/today/{username}")
async def get_today_polythene_entries(username: str):
    """Get today's polythene entries by user"""
    today = datetime.now(timezone.utc).date().isoformat()
    
    entries = await db.polythene_adjustments.find(
        {'adjusted_by': username, 'date': today},
        {"_id": 0}
    ).to_list(100)
    
    return entries

@api_router.delete("/polythene/{entry_id}")
async def delete_polythene_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a polythene entry"""
    result = await db.polythene_adjustments.delete_one({'id': entry_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Entry not found")
    
    return {'success': True}

# ==================== ADMIN ACCOUNTABILITY ====================

@api_router.get("/activity-log")
async def get_activity_log(current_user: dict = Depends(get_current_user)):
    """Get complete activity log for admin accountability"""
    
    if current_user['role'] != 'admin':
        raise HTTPException(status_code=403, detail="Admin only")
    
    activities = await db.activity_log.find({}, {"_id": 0}).sort('timestamp', -1).limit(200).to_list(200)
    return activities


    return {'success': True}

@api_router.get("/transactions")
async def get_transactions(type: Optional[str] = None, limit: int = 5000):
    """Get all transactions"""
    query = {} if not type else {"type": type}
    transactions = await db.transactions.find(query, {"_id": 0}).sort("date", -1).to_list(limit)
    return transactions

@api_router.get("/inventory/current")
async def get_current_inventory():
    """Calculate current inventory: Opening Stock + Purchases - Sales"""
    
    # Items to always exclude from inventory
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]
    
    # Get opening stock and transactions
    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(10000)
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(10000)
    
    # Get all item mappings
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(10000)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in mappings}
    
    # Get master items for stamp lookup
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(10000)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}
    
    # Filter out excluded items
    opening = [item for item in opening if item['item_name'] not in EXCLUDED_ITEMS]
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS]
    
    # Build inventory map starting with opening stock
    inventory_map = {}
    
    # Add all opening stock items
    for item in opening:
        key = item['item_name'].strip().lower()
        if key not in inventory_map:
            inventory_map[key] = {
                'item_name': item['item_name'],
                'stamp': item.get('stamp', '') or 'Unassigned',
                'stamp_locked': bool(item.get('stamp')),  # Lock stamp from STOCK 2026
                'gr_wt': 0.0,
                'net_wt': 0.0,
                'fine': 0.0,
                'total_pc': 0,
                'labor': 0.0,
                'stamps_seen': set()
            }
        inventory_map[key]['gr_wt'] += item.get('gr_wt', 0)
        inventory_map[key]['net_wt'] += item.get('net_wt', 0)
        inventory_map[key]['fine'] += item.get('fine', 0)
        inventory_map[key]['total_pc'] += item.get('pc', 0)
        inventory_map[key]['labor'] += item.get('total', 0)
        if item.get('stamp'):
            inventory_map[key]['stamps_seen'].add(item['stamp'])
            inventory_map[key]['stamp'] = item['stamp']  # Opening stock stamp is final
    
    # Process all transactions
    for trans in transactions:
        trans_name = trans['item_name'].strip()
        
        # Check if this transaction name has a mapping
        master_name = mapping_dict.get(trans_name, trans_name)
        
        # Use master name for grouping
        key = master_name.strip().lower()
        
        if key not in inventory_map:
            # New item not in opening stock
            # Get stamp from master_items if it exists there
            item_stamp = master_stamp_dict.get(master_name, trans.get('stamp', 'Unassigned'))
            
            inventory_map[key] = {
                'item_name': master_name,
                'stamp': item_stamp,
                'stamp_locked': master_name in master_stamp_dict,
                'gr_wt': 0.0,
                'net_wt': 0.0,
                'fine': 0.0,
                'total_pc': 0,
                'labor': 0.0,
                'stamps_seen': set()
            }
        
        # Track stamps seen but don't override if locked
        if trans.get('stamp') and not inventory_map[key].get('stamp_locked', False):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])
            inventory_map[key]['stamp'] = trans['stamp']
        elif trans.get('stamp'):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])
        
        # Weights in Excel already include negatives for returns
        # Purchase types (P, PR): ADD to stock
        # Sale types (S, SR): SUBTRACT from stock
        multiplier = 1 if trans['type'] in ['purchase', 'purchase_return'] else -1
        
        inventory_map[key]['gr_wt'] += trans.get('gr_wt', 0) * multiplier
        inventory_map[key]['net_wt'] += trans.get('net_wt', 0) * multiplier
        inventory_map[key]['fine'] += trans.get('fine', 0) * multiplier
        inventory_map[key]['total_pc'] += trans.get('total_pc', 0) * multiplier
        inventory_map[key]['labor'] += trans.get('labor', 0) * multiplier
    
    # Convert to list and separate negative items
    inventory = []
    negative_items = []
    total_gr_wt = 0.0
    total_net_wt = 0.0
    
    for key, item in inventory_map.items():
        item['stamps_seen'] = list(item['stamps_seen']) if isinstance(item['stamps_seen'], set) else item['stamps_seen']
        
        # Always include in total calculation (even negative items)
        total_gr_wt += item['gr_wt']
        total_net_wt += item['net_wt']
        
        # Separate negative stock items for display
        if item['gr_wt'] < -0.01 or item['net_wt'] < -0.01:
            negative_items.append(item)
        else:
            inventory.append(item)
    
    # Group by stamp
    stamp_groups = {}
    for item in inventory:
        stamp = item['stamp'] or 'Unassigned'
        if stamp not in stamp_groups:
            stamp_groups[stamp] = []
        stamp_groups[stamp].append(item)
    
    return {
        "inventory": inventory,
        "by_stamp": stamp_groups,
        "total_items": len(inventory),
        "total_gr_wt": total_gr_wt,
        "total_net_wt": total_net_wt,
        "negative_items": negative_items
    }

@api_router.post("/physical-stock/upload")
async def upload_physical_stock(
    file: UploadFile = File(...),
    verification_date: Optional[str] = None
):
    """Upload physical stock file with verification date"""
    content = await file.read()
    
    try:
        # Parse using opening_stock parser (same format)
        records = parse_excel_file(content, 'opening_stock')
        
        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in file")
        
        # MERGE items by name
        merged_items = {}
        for record in records:
            key = record['item_name'].strip().lower()
            if key not in merged_items:
                merged_items[key] = {
                    'item_name': record['item_name'],
                    'stamp': record.get('stamp', ''),
                    'pc': 0,
                    'gr_wt': 0.0,
                    'net_wt': 0.0,
                    'fine': 0.0,
                    'verification_date': verification_date or datetime.now(timezone.utc).isoformat()
                }
            
            # Sum weights
            merged_items[key]['gr_wt'] += record.get('gr_wt', 0)
            merged_items[key]['net_wt'] += record.get('net_wt', 0)
            merged_items[key]['fine'] += record.get('fine', 0)
            merged_items[key]['pc'] += record.get('pc', 0)
            
            # Keep stamp if this entry has one
            if record.get('stamp') and not merged_items[key]['stamp']:
                merged_items[key]['stamp'] = record['stamp']
        
        # Clear existing physical stock
        await db.physical_stock.delete_many({})
        
        # Insert merged items
        stock_items = [PhysicalStock(**item).model_dump() for item in merged_items.values()]
        await db.physical_stock.insert_many(stock_items)
        
        # Calculate totals
        total_net_wt = sum(item['net_wt'] for item in stock_items)
        total_gr_wt = sum(item['gr_wt'] for item in stock_items)
        
        return {
            "success": True,
            "count": len(stock_items),
            "original_rows": len(records),
            "merged_items": len(stock_items),
            "total_net_wt_kg": round(total_net_wt/1000, 3),
            "total_gr_wt_kg": round(total_gr_wt/1000, 3),
            "verification_date": verification_date,
            "message": f"Physical stock uploaded: {len(stock_items)} items, {total_net_wt/1000:.3f} kg" + (f" (verified on {verification_date})" if verification_date else "")
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error processing file: {str(e)}")

@api_router.get("/physical-stock/compare")
async def compare_physical_with_book():
    """Compare physical stock with book stock and show differences"""
    
    # Get book stock (current inventory)
    book_response = await get_current_inventory()
    book_items = {item['item_name'].strip().lower(): item for item in book_response['inventory']}
    book_items.update({item['item_name'].strip().lower(): item for item in book_response['negative_items']})
    
    # Get physical stock
    physical = await db.physical_stock.find({}, {"_id": 0}).to_list(10000)
    physical_items = {item['item_name'].strip().lower(): item for item in physical}
    
    # Compare
    matches = []
    discrepancies = []
    only_in_book = []
    only_in_physical = []
    
    # Check items in both
    for key in book_items.keys():
        if key in physical_items:
            book_item = book_items[key]
            phys_item = physical_items[key]
            
            book_net = book_item['net_wt']
            phys_net = phys_item['net_wt']
            diff = phys_net - book_net
            
            comparison = {
                'item_name': book_item['item_name'],
                'stamp': book_item.get('stamp', ''),
                'book_net_wt': book_net,
                'physical_net_wt': phys_net,
                'difference': diff,
                'difference_kg': round(diff/1000, 3),
                'match_percentage': round((min(book_net, phys_net) / max(book_net, phys_net) * 100) if max(book_net, phys_net) > 0 else 100, 2)
            }
            
            if abs(diff) < 10:
                matches.append(comparison)
            else:
                discrepancies.append(comparison)
    
    # Items only in book
    for key in book_items.keys():
        if key not in physical_items:
            only_in_book.append({
                'item_name': book_items[key]['item_name'],
                'stamp': book_items[key].get('stamp', ''),
                'book_net_wt': book_items[key]['net_wt'],
                'book_net_wt_kg': round(book_items[key]['net_wt']/1000, 3)
            })
    
    # Items only in physical
    for key in physical_items.keys():
        if key not in book_items:
            only_in_physical.append({
                'item_name': physical_items[key]['item_name'],
                'stamp': physical_items[key].get('stamp', ''),
                'physical_net_wt': physical_items[key]['net_wt'],
                'physical_net_wt_kg': round(physical_items[key]['net_wt']/1000, 3)
            })
    
    discrepancies.sort(key=lambda x: abs(x['difference']), reverse=True)
    
    total_book = sum(item['net_wt'] for item in book_items.values())
    total_physical = sum(item['net_wt'] for item in physical_items.values())
    
    return {
        "summary": {
            "total_book_kg": round(total_book/1000, 3),
            "total_physical_kg": round(total_physical/1000, 3),
            "total_difference_kg": round((total_physical - total_book)/1000, 3),
            "match_count": len(matches),
            "discrepancy_count": len(discrepancies),
            "only_in_book_count": len(only_in_book),
            "only_in_physical_count": len(only_in_physical)
        },
        "matches": matches[:50],
        "discrepancies": discrepancies[:50],
        "only_in_book": only_in_book[:50],
        "only_in_physical": only_in_physical[:50]
    }

@api_router.get("/history/recent-uploads")
async def get_recent_uploads():
    """Get last 5 file uploads for undo selection"""
    actions = await db.action_history.find(
        {"action_type": {"$in": ["upload_purchase", "upload_sale"]}},
        {"_id": 0}
    ).sort("timestamp", -1).limit(5).to_list(5)
    
    return actions


@api_router.get("/inventory/stamp-breakdown/{stamp}")
async def get_stamp_breakdown(stamp: str):
    """Get detailed breakdown for a specific stamp (opening + purchases - sales)"""
    
    # Get opening stock for this stamp
    opening = await db.opening_stock.find({"stamp": stamp}, {"_id": 0}).to_list(1000)
    stamp_item_names = [item['item_name'] for item in opening]
    
    # Get mappings to this stamp's items
    all_mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(10000)
    mapped_names = [m['transaction_name'] for m in all_mappings if m['master_name'] in stamp_item_names]
    
    # All names that belong to this stamp
    all_names = stamp_item_names + mapped_names
    
    # Calculate opening totals
    opening_gross = sum(item.get('gr_wt', 0) for item in opening)
    opening_net = sum(item.get('net_wt', 0) for item in opening)
    
    # Get purchases for these items
    purchases = await db.transactions.find({
        "item_name": {"$in": all_names},
        "type": {"$in": ["purchase", "purchase_return"]}
    }, {"_id": 0}).to_list(10000)
    
    purchase_gross = sum(t.get('gr_wt', 0) for t in purchases)
    purchase_net = sum(t.get('net_wt', 0) for t in purchases)
    
    # Get sales for these items
    sales = await db.transactions.find({
        "item_name": {"$in": all_names},
        "type": {"$in": ["sale", "sale_return"]}
    }, {"_id": 0}).to_list(10000)
    
    sale_gross = sum(t.get('gr_wt', 0) for t in sales)
    sale_net = sum(t.get('net_wt', 0) for t in sales)
    
    # Current = Opening + Purchases - Sales
    current_gross = opening_gross + purchase_gross - sale_gross
    current_net = opening_net + purchase_net - sale_net
    
    return {
        "stamp": stamp,
        "opening_gross": opening_gross,
        "opening_net": opening_net,
        "purchase_gross": purchase_gross,
        "purchase_net": purchase_net,
        "sale_gross": sale_gross,
        "sale_net": sale_net,
        "current_gross": current_gross,
        "current_net": current_net,
        "item_count": len(stamp_item_names),
        "mapped_count": len(mapped_names)
    }


@api_router.post("/history/undo-upload")
async def undo_upload(batch_id: str):
    """Undo a specific file upload by batch_id"""
    
    # Find the action
    action = await db.action_history.find_one({"data_snapshot.batch_id": batch_id})
    if not action:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    # Delete all transactions with this batch_id
    delete_result = await db.transactions.delete_many({"batch_id": batch_id})
    
    # Mark action as undone
    await db.action_history.update_one(
        {"data_snapshot.batch_id": batch_id},
        {"$set": {"can_undo": False}}
    )
    
    return {
        "success": True,
        "message": f"Undone: {action.get('description', 'Upload')}",
        "deleted_count": delete_result.deleted_count
    }


    only_in_physical = []
    
    # Check items in both
    for key in book_items.keys():
        if key in physical_items:
            book_item = book_items[key]
            phys_item = physical_items[key]
            
            book_net = book_item['net_wt']
            phys_net = phys_item['net_wt']
            diff = phys_net - book_net
            
            comparison = {
                'item_name': book_item['item_name'],
                'stamp': book_item.get('stamp', ''),
                'book_net_wt': book_net,
                'physical_net_wt': phys_net,
                'difference': diff,
                'difference_kg': round(diff/1000, 3),
                'match_percentage': round((min(book_net, phys_net) / max(book_net, phys_net) * 100) if max(book_net, phys_net) > 0 else 100, 2)
            }
            
            # Consider it a match if difference is less than 0.01 kg (10 grams)
            if abs(diff) < 10:
                matches.append(comparison)
            else:
                discrepancies.append(comparison)
    
    # Items only in book stock
    for key in book_items.keys():
        if key not in physical_items:
            only_in_book.append({
                'item_name': book_items[key]['item_name'],
                'stamp': book_items[key].get('stamp', ''),
                'book_net_wt': book_items[key]['net_wt'],
                'book_net_wt_kg': round(book_items[key]['net_wt']/1000, 3)
            })
    
    # Items only in physical stock
    for key in physical_items.keys():
        if key not in book_items:
            only_in_physical.append({
                'item_name': physical_items[key]['item_name'],
                'stamp': physical_items[key].get('stamp', ''),
                'physical_net_wt': physical_items[key]['net_wt'],
                'physical_net_wt_kg': round(physical_items[key]['net_wt']/1000, 3)
            })
    
    # Sort discrepancies by absolute difference
    discrepancies.sort(key=lambda x: abs(x['difference']), reverse=True)
    
    # Calculate totals
    total_book = sum(item['net_wt'] for item in book_items.values())
    total_physical = sum(item['net_wt'] for item in physical_items.values())
    
    return {
        "summary": {
            "total_book_kg": round(total_book/1000, 3),
            "total_physical_kg": round(total_physical/1000, 3),
            "total_difference_kg": round((total_physical - total_book)/1000, 3),
            "match_count": len(matches),
            "discrepancy_count": len(discrepancies),
            "only_in_book_count": len(only_in_book),
            "only_in_physical_count": len(only_in_physical)
        },
        "matches": matches[:50],
        "discrepancies": discrepancies[:50],
        "only_in_book": only_in_book[:50],
        "only_in_physical": only_in_physical[:50]
    }

@api_router.post("/master-stock/upload")
async def upload_master_stock(file: UploadFile = File(...)):
    """Upload STOCK 2026 as master reference - FINAL item names and stamps"""
    content = await file.read()
    
    try:
        df = pd.read_excel(BytesIO(content), header=0)
        df = df.fillna('')
        df.columns = df.columns.str.strip()
        
        # Remove totals row
        df = df[~df['Item Name'].astype(str).str.lower().str.contains('total', na=False)]
        
        # Clear existing opening stock and master items
        await db.opening_stock.delete_many({})
        await db.master_items.delete_many({})
        
        opening_items = []
        master_items = []
        
        for _, row in df.iterrows():
            item_name = str(row.get('Item Name', '')).strip()
            if not item_name or len(item_name) < 2:
                continue
            
            stamp = str(row.get('Stamp', '')).strip()
            gr_wt = float(row.get('Gross weigth', 0) or 0)
            net_wt = float(row.get('Net Weight', 0) or 0)
            
            # Opening stock
            opening_items.append({
                'item_name': item_name,
                'stamp': stamp,
                'unit': 'kg',
                'pc': 0,
                'gr_wt': gr_wt,
                'net_wt': net_wt,
                'fine': 0.0,
                'labor_wt': 0.0,
                'labor_rs': 0.0,
                'rate': 0.0,
                'total': 0.0
            })
            
            # Master reference
            master_items.append({
                'item_name': item_name,
                'stamp': stamp,
                'gr_wt': gr_wt,
                'net_wt': net_wt,
                'is_master': True
            })
        
        await db.opening_stock.insert_many(opening_items)
        await db.master_items.insert_many(master_items)
        
        total_net = sum(i['net_wt'] for i in opening_items)
        
        return {
            "success": True,
            "count": len(opening_items),
            "total_net_kg": round(total_net / 1000, 3),
            "message": f"Master stock uploaded: {len(opening_items)} items, {total_net/1000:.3f} kg"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@api_router.post("/purchase-ledger/upload")
async def upload_purchase_ledger(file: UploadFile = File(...)):
    """Upload PURCHASE_CUMUL file to create/update purchase rate ledger"""
    content = await file.read()
    
    try:
        df = pd.read_excel(BytesIO(content), header=2)
        df = df.fillna(0)
        df.columns = df.columns.str.strip()
        
        await db.purchase_ledger.delete_many({})
        
        ledger_items = []
        
        for _, row in df.iterrows():
            item_name = str(row.get('Particular', '')).strip()
            if not item_name or len(item_name) < 2:
                continue
            
            if 'total' in item_name.lower():
                continue
            
            less = float(row.get('Less', 0) or 0)
            sil_fine = float(row.get('Sil.Fine', 0) or 0)
            total = float(row.get('Total', 0) or 0)
            
            if less > 0:
                purchase_tunch = (sil_fine / less * 100)
                labour_per_kg = (total / less)
                
                ledger_items.append({
                    'item_name': item_name,
                    'purchase_tunch': purchase_tunch,
                    'labour_per_kg': labour_per_kg,
                    'total_purchased_kg': less,
                    'total_fine_kg': sil_fine,
                    'total_labour': total
                })
        
        if ledger_items:
            await db.purchase_ledger.insert_many(ledger_items)
        
        return {
            "success": True,
            "count": len(ledger_items),
            "message": f"Purchase ledger created with {len(ledger_items)} items"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error: {str(e)}")

@api_router.get("/analytics/customer-profit")
async def get_customer_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Calculate profit per customer (silver & labour)"""
    
    query = {}
    if start_date and end_date:
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    # Get all sales
    sales = await db.transactions.find(
        {**query, "type": {"$in": ["sale", "sale_return"]}},
        {"_id": 0}
    ).to_list(10000)
    
    # Get purchase ledger
    ledger = await db.purchase_ledger.find({}, {"_id": 0}).to_list(10000)
    ledger_map = {item['item_name']: item for item in ledger}
    
    # Group by customer
    customer_profit = defaultdict(lambda: {
        'customer_name': '',
        'silver_profit_kg': 0.0,
        'labour_profit_inr': 0.0,
        'total_sold_kg': 0.0,
        'transaction_count': 0
    })
    
    for sale in sales:
        customer = sale.get('party_name', 'Unknown')
        if not customer:
            continue
        
        item_name = sale.get('item_name', '')
        sale_tunch = float(sale.get('tunch', 0) or 0)
        sale_net_wt = sale.get('net_wt', 0)
        sale_labour = sale.get('labor', 0)
        
        # Get purchase rates from ledger
        ledger_item = ledger_map.get(item_name)
        if ledger_item:
            purchase_tunch = ledger_item.get('purchase_tunch', 0)
            purchase_labour_per_gram = ledger_item.get('labour_per_kg', 0) / 1000
        else:
            purchase_tunch = 0
            purchase_labour_per_gram = 0
        
        # Calculate profit for this transaction
        silver_profit_grams = (sale_tunch - purchase_tunch) * sale_net_wt / 100
        silver_profit_kg = silver_profit_grams / 1000
        
        sale_labour_per_gram = sale_labour / sale_net_wt if sale_net_wt > 0 else 0
        labour_profit = (sale_labour_per_gram - purchase_labour_per_gram) * sale_net_wt
        
        customer_profit[customer]['customer_name'] = customer
        customer_profit[customer]['silver_profit_kg'] += silver_profit_kg
        customer_profit[customer]['labour_profit_inr'] += labour_profit
        customer_profit[customer]['total_sold_kg'] += sale_net_wt / 1000
        customer_profit[customer]['transaction_count'] += 1
    
    # Convert to list and sort
    customers = sorted(
        [v for v in customer_profit.values()],
        key=lambda x: x['silver_profit_kg'],
        reverse=True
    )
    
    return {
        "customers": customers,
        "total_customers": len(customers)
    }

@api_router.get("/analytics/supplier-profit")
async def get_supplier_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Calculate profit per supplier (based on items purchased from them)"""
    
    query = {}
    if start_date and end_date:
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    # Get all purchases
    purchases = await db.transactions.find(
        {**query, "type": {"$in": ["purchase", "purchase_return"]}},
        {"_id": 0}
    ).to_list(10000)
    
    # Group by supplier with cumulative purchase data
    supplier_data = defaultdict(lambda: {
        'supplier_name': '',
        'total_purchased_kg': 0.0,
        'transaction_count': 0,
        'items': defaultdict(lambda: {'net_wt': 0, 'tunch': 0, 'labour': 0})
    })
    
    for purchase in purchases:
        supplier = purchase.get('party_name', 'Unknown')
        if not supplier:
            continue
        
        item_name = purchase.get('item_name', '')
        purchase_tunch = float(purchase.get('tunch', 0) or 0)
        purchase_net_wt = purchase.get('net_wt', 0)
        purchase_labour = purchase.get('labor', 0)
        
        supplier_data[supplier]['supplier_name'] = supplier
        supplier_data[supplier]['total_purchased_kg'] += purchase_net_wt / 1000
        supplier_data[supplier]['transaction_count'] += 1
        
        # Track per-item data for this supplier
        supplier_data[supplier]['items'][item_name]['net_wt'] += purchase_net_wt
        supplier_data[supplier]['items'][item_name]['tunch'] += purchase_tunch * abs(purchase_net_wt)
        supplier_data[supplier]['items'][item_name]['labour'] += purchase_labour
    
    # Note: Supplier profit requires knowing what we sold those items for
    # This is complex - for now just return purchase data
    suppliers = sorted(
        [v for v in supplier_data.values()],
        key=lambda x: x['total_purchased_kg'],
        reverse=True
    )
    
    return {
        "suppliers": suppliers,
        "total_suppliers": len(suppliers),
        "note": "Supplier profit requires matching sold items - placeholder for now"
    }


@api_router.get("/purchase-ledger/all")
async def get_purchase_ledger():
    """Get all purchase rate ledger items"""
    ledger = await db.purchase_ledger.find({}, {"_id": 0}).sort("item_name", 1).to_list(10000)
    return ledger

@api_router.get("/mappings/unmapped")
async def get_unmapped_items():
    """Get all unmapped items from transactions"""
    # Get all transaction item names
    transactions = await db.transactions.find({}, {"_id": 0, "item_name": 1}).to_list(10000)
    trans_names = set(t['item_name'] for t in transactions)
    
    # Get all master item names
    master = await db.master_items.find({}, {"_id": 0, "item_name": 1}).to_list(10000)
    master_names = set(m['item_name'] for m in master)
    
    # Get existing mappings
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(10000)
    mapped_names = set(m['transaction_name'] for m in mappings)
    
    # Find unmapped: in transactions but not in master and not already mapped
    unmapped = []
    for name in trans_names:
        if name not in master_names and name not in mapped_names:
            unmapped.append(name)
    
    return {
        "unmapped_items": sorted(unmapped),
        "count": len(unmapped)
    }

@api_router.post("/mappings/create")
async def create_mapping(transaction_name: str, master_name: str):
    """Create a mapping from transaction name to master name"""
    # Verify master name exists
    master = await db.master_items.find_one({"item_name": master_name}, {"_id": 0})
    if not master:
        raise HTTPException(status_code=404, detail="Master item not found")
    
    # Check if mapping already exists
    existing = await db.item_mappings.find_one({"transaction_name": transaction_name})
    if existing:
        # Update existing
        await db.item_mappings.update_one(
            {"transaction_name": transaction_name},
            {"$set": {"master_name": master_name}}
        )
    else:
        # Create new
        mapping = ItemMapping(
            transaction_name=transaction_name,
            master_name=master_name
        )
        await db.item_mappings.insert_one(mapping.model_dump())
    
    return {"success": True, "message": f"Mapped '{transaction_name}' → '{master_name}'"}

@api_router.post("/stamp-verification/save")
async def save_stamp_verification(
    stamp: str,
    physical_gross_wt: float,
    book_gross_wt: float,
    difference: float,
    is_match: bool,
    verification_date: str
):
    """Save stamp verification record"""
    
    # Save to history
    await save_action(
        'stamp_verification',
        f"{stamp} verified: {'MATCH' if is_match else 'MISMATCH'} (Diff: {difference/1000:.3f} kg)",
        {
            'stamp': stamp,
            'physical_gross_wt': physical_gross_wt,
            'book_gross_wt': book_gross_wt,
            'difference': difference,
            'is_match': is_match,
            'verification_date': verification_date
        }
    )
    
    # Save stamp verification record
    verification = {
        'stamp': stamp,
        'physical_gross_wt': physical_gross_wt,
        'book_gross_wt': book_gross_wt,
        'difference': difference,
        'is_match': is_match,
        'verification_date': verification_date,
        'verified_at': datetime.now(timezone.utc).isoformat()
    }
    
    # Update or insert
    await db.stamp_verifications.update_one(
        {'stamp': stamp, 'verification_date': verification_date},
        {'$set': verification},
        upsert=True
    )
    
    # Check if all stamps verified
    total_stamps = await db.master_items.distinct('stamp')
    verified_stamps = await db.stamp_verifications.distinct('stamp', {'verification_date': verification_date})
    
    notification_msg = f"{stamp} {'matched' if is_match else 'mismatched'}"
    
    if len(verified_stamps) >= len(total_stamps):
        notification_msg += " - ALL STAMPS VERIFIED!"
        
        # Create notification for admin
        await db.notifications.insert_one({
            'type': 'full_stock_match',
            'message': f'Full stock verification complete for {verification_date}',
            'severity': 'success',
            'for_role': 'admin',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    else:
        # Individual stamp notification
        await db.notifications.insert_one({
            'type': 'stamp_verification',
            'message': notification_msg,
            'severity': 'warning' if not is_match else 'info',
            'for_role': 'admin',
            'stamp': stamp,
            'is_match': is_match,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'read': False
        })
    
    return {
        'success': True,
        'message': notification_msg,
        'verified_stamps': len(verified_stamps),
        'total_stamps': len(total_stamps)
    }

@api_router.get("/mappings/all")
async def get_all_mappings():
    """Get all item mappings"""
    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(10000)
    return mappings

@api_router.delete("/mappings/{transaction_name}")
async def delete_mapping(transaction_name: str):
    """Delete a mapping"""
    result = await db.item_mappings.delete_one({"transaction_name": transaction_name})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return {"success": True, "message": "Mapping deleted"}

@api_router.get("/master-items")
async def get_master_items(search: Optional[str] = None):
    """Get all master items with optional search"""
    query = {}
    if search:
        query = {"item_name": {"$regex": search, "$options": "i"}}
    
    items = await db.master_items.find(query, {"_id": 0}).sort("item_name", 1).to_list(1000)
    return items

@api_router.get("/analytics/party-analysis")
async def get_party_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Analyze parties (customers and suppliers) with silver weight comparisons"""
    
    query = {}
    if start_date and end_date:
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    transactions = await db.transactions.find(query, {"_id": 0}).to_list(10000)
    
    customers = defaultdict(lambda: {
        'party_name': '',
        'total_sales_value': 0.0,
        'total_net_wt': 0.0,
        'total_fine_wt': 0.0,
        'total_gr_wt': 0.0,
        'transaction_count': 0
    })
    
    suppliers = defaultdict(lambda: {
        'party_name': '',
        'total_purchases_value': 0.0,
        'total_net_wt': 0.0,
        'total_fine_wt': 0.0,
        'total_gr_wt': 0.0,
        'transaction_count': 0
    })
    
    for trans in transactions:
        party = trans.get('party_name', 'Unknown')
        if not party:
            continue
        
        amount = trans.get('total_amount', 0)
        net_wt = trans.get('net_wt', 0)
        fine_wt = trans.get('fine', 0)
        gr_wt = trans.get('gr_wt', 0)
        
        if trans['type'] in ['sale', 'sale_return']:
            multiplier = 1 if trans['type'] == 'sale' else -1
            customers[party]['party_name'] = party
            customers[party]['total_sales_value'] += amount * multiplier
            customers[party]['total_net_wt'] += net_wt * multiplier
            customers[party]['total_fine_wt'] += fine_wt * multiplier
            customers[party]['total_gr_wt'] += gr_wt * multiplier
            customers[party]['transaction_count'] += 1
        
        elif trans['type'] in ['purchase', 'purchase_return']:
            multiplier = 1 if trans['type'] == 'purchase' else -1
            suppliers[party]['party_name'] = party
            suppliers[party]['total_purchases_value'] += amount * multiplier
            suppliers[party]['total_net_wt'] += net_wt * multiplier
            suppliers[party]['total_fine_wt'] += fine_wt * multiplier
            suppliers[party]['total_gr_wt'] += gr_wt * multiplier
            suppliers[party]['transaction_count'] += 1
    
    # Convert to lists and sort by net weight
    customers_list = sorted(
        [v for v in customers.values()],
        key=lambda x: x['total_net_wt'],
        reverse=True
    )
    
    suppliers_list = sorted(
        [v for v in suppliers.values()],
        key=lambda x: x['total_net_wt'],
        reverse=True
    )
    
    return {
        "customers": customers_list[:50],
        "suppliers": suppliers_list[:50],
        "top_customer": customers_list[0] if customers_list else None,
        "top_supplier": suppliers_list[0] if suppliers_list else None
    }

@api_router.get("/analytics/sales-summary")
async def get_sales_summary(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get total sales summary with net weight, fine weight, and labour (including returns)"""
    
    # Items to exclude
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]
    
    query = {"type": {"$in": ["sale", "sale_return"]}}
    if start_date and end_date:
        query['date'] = {'$gte': start_date, '$lte': end_date}
    
    # Get ALL sale transactions (S and SR - SR have negative values already)
    sales_transactions = await db.transactions.find(query, {"_id": 0}).to_list(10000)
    
    # Filter out excluded items
    sales_transactions = [t for t in sales_transactions if t['item_name'] not in EXCLUDED_ITEMS]
    
    # Sum including negative values (SR rows are already negative)
    total_net_wt = sum(t.get('net_wt', 0) for t in sales_transactions)
    total_fine_wt = sum(t.get('fine', 0) for t in sales_transactions)
    total_labor = sum(t.get('labor', 0) for t in sales_transactions)
    total_sales_value = sum(t.get('total_amount', 0) for t in sales_transactions)
    
    return {
        "total_net_wt_kg": round(total_net_wt / 1000, 3),
        "total_fine_wt_kg": round(total_fine_wt / 1000, 3),
        "total_labor": round(total_labor, 2),
        "total_sales_value": round(total_sales_value, 2),
        "transaction_count": len(sales_transactions)
    }

@api_router.get("/analytics/profit")
async def calculate_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Calculate profit: Silver profit (in kg) and Labour profit (in INR)"""
    
    # Items to exclude from profit calculation
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS", "COURIER", "EMERALD MURTI", "FRAME NEW", "NAJARIA"]
    
    query = {}
    if start_date and end_date:
        # Add time component to end_date to include full day
        end_date_with_time = end_date + ' 23:59:59'
        query['date'] = {'$gte': start_date, '$lte': end_date_with_time}
    
    transactions = await db.transactions.find(query, {"_id": 0}).to_list(10000)
    
    # Filter out excluded items
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS]
    
    # Fetch ALL purchase ledger items upfront (for items sold from opening stock)
    all_ledger = await db.purchase_ledger.find({}, {"_id": 0}).to_list(10000)
    ledger_map = {item['item_name']: item for item in all_ledger}
    
    # Group transactions by item for profit calculation
    item_transactions = defaultdict(lambda: {'purchases': [], 'sales': []})
    
    for trans in transactions:
        item_name = trans.get('item_name', '')
        if not item_name:
            continue
        
        trans_data = {
            'date': trans.get('date'),
            'net_wt': trans.get('net_wt', 0),
            'tunch': float(trans.get('tunch', 0) or 0),
            'labor': trans.get('labor', 0),
            'total_amount': trans.get('total_amount', 0)
        }
        
        if trans['type'] in ['purchase', 'purchase_return']:
            item_transactions[item_name]['purchases'].append(trans_data)
        elif trans['type'] in ['sale', 'sale_return']:
            item_transactions[item_name]['sales'].append(trans_data)
    
    # Calculate profits per user's formula
    total_silver_profit_kg = 0.0  # Silver profit in KG
    total_labor_profit_inr = 0.0  # Labour profit in INR
    item_profits = []
    
    for item_name, data in item_transactions.items():
        purchases = data['purchases']
        sales = data['sales']
        
        # Skip if no sales
        if not sales:
            continue
        
        # If no purchases in this period, try to get cost basis from purchase ledger
        if not purchases:
            ledger_item = ledger_map.get(item_name)
            if ledger_item:
                # Use cumulative purchase data as cost basis
                purchases = [{
                    'net_wt': ledger_item.get('total_purchased_kg', 0) * 1000,  # Convert to grams
                    'tunch': ledger_item.get('purchase_tunch', 0),
                    'labor': ledger_item.get('labour_per_kg', 0)
                }]
            else:
                # No purchase history - skip this item
                continue
        
        # Calculate total and average values
        total_purchase_wt = sum(p['net_wt'] for p in purchases)
        total_sale_wt = sum(s['net_wt'] for s in sales)
        
        if abs(total_purchase_wt) < 0.001 or abs(total_sale_wt) < 0.001:
            continue
        
        # Average tunch weighted by ABSOLUTE net weight (to handle negative returns correctly)
        avg_purchase_tunch = sum(p['tunch'] * abs(p['net_wt']) for p in purchases) / sum(abs(p['net_wt']) for p in purchases) if purchases else 0
        avg_sale_tunch = sum(s['tunch'] * abs(s['net_wt']) for s in sales) / sum(abs(s['net_wt']) for s in sales) if sales else 0
        
        # Labour per kg calculation
        # Purchase ledger has labour_per_kg (per kilogram)
        # Sales have labor (total) and net_wt (in grams)
        # Need to calculate both in same unit (per gram)
        
        # Purchase: labour_per_kg → labour_per_gram
        purchase_labour_per_gram = sum(abs(p['labor']) / 1000 for p in purchases) / sum(abs(p['net_wt']) for p in purchases) if purchases else 0
        
        # Sale: total labour / total grams
        sale_labour_per_gram = sum(abs(s['labor']) for s in sales) / sum(abs(s['net_wt']) for s in sales) if sales else 0
        
        # USER'S FORMULA:
        # 1. Silver Profit (kg) = (sale tunch - purchase tunch) * sale net weight / 100
        silver_profit_grams = (avg_sale_tunch - avg_purchase_tunch) * total_sale_wt / 100
        silver_profit_kg = silver_profit_grams / 1000  # Convert to kg
        
        # 2. Labour Profit (INR) = (sale labour per gram - purchase labour per gram) * sale net weight (grams)
        labor_profit_inr = (sale_labour_per_gram - purchase_labour_per_gram) * total_sale_wt
        
        total_silver_profit_kg += silver_profit_kg
        total_labor_profit_inr += labor_profit_inr
        
        item_profits.append({
            'item_name': item_name,
            'silver_profit_kg': round(silver_profit_kg, 3),
            'labor_profit_inr': round(labor_profit_inr, 2),
            'avg_purchase_tunch': round(avg_purchase_tunch, 2),
            'avg_sale_tunch': round(avg_sale_tunch, 2),
            'net_wt_sold_kg': round(total_sale_wt / 1000, 3)
        })
    
    # Sort by silver profit
    item_profits.sort(key=lambda x: x['silver_profit_kg'], reverse=True)
    
    # Calculate total sales/purchases value
    total_sales_value = sum(t['total_amount'] for t in transactions if t['type'] == 'sale')
    total_purchase_value = sum(t['total_amount'] for t in transactions if t['type'] == 'purchase')
    
    return {
        "silver_profit_kg": round(total_silver_profit_kg, 3),
        "labor_profit_inr": round(total_labor_profit_inr, 2),
        "total_sales_value": round(total_sales_value, 2),
        "total_purchase_value": round(total_purchase_value, 2),
        "top_profitable_items": item_profits[:20],
        "least_profitable_items": item_profits[-20:] if len(item_profits) > 20 else [],
        "total_items_analyzed": len(item_profits)
    }

@api_router.get("/history/actions")
async def get_action_history(limit: int = 20):
    """Get recent actions for undo/redo"""
    actions = await db.action_history.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return actions

@api_router.post("/history/undo")
async def undo_last_action():
    """Undo last action"""
    last_action = await db.action_history.find_one({"can_undo": True}, sort=[("timestamp", -1)])
    
    if not last_action:
        raise HTTPException(status_code=404, detail="No action to undo")
    
    # Mark as undone
    await db.action_history.update_one(
        {"id": last_action['id']},
        {"$set": {"can_undo": False}}
    )
    
    return {
        "success": True,
        "message": f"Undone: {last_action['description']}",
        "action": last_action
    }

@api_router.post("/system/reset")
async def reset_system(request: ResetRequest):
    """Reset entire system with password protection"""
    if request.password != "CLOSE":
        raise HTTPException(status_code=403, detail="Invalid password")
    
    # Clear all collections
    await db.transactions.delete_many({})
    await db.opening_stock.delete_many({})
    await db.action_history.delete_many({})
    
    return {
        "success": True,
        "message": "System reset successfully. All data cleared."
    }

@api_router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    total_transactions = await db.transactions.count_documents({})
    total_purchases = await db.transactions.count_documents({"type": "purchase"})
    total_sales = await db.transactions.count_documents({"type": "sale"})
    total_opening_stock = await db.opening_stock.count_documents({})
    
    # Get unique parties
    all_parties = await db.transactions.distinct("party_name")
    total_parties = len([p for p in all_parties if p])
    
    return {
        "total_transactions": total_transactions,
        "total_purchases": total_purchases,
        "total_sales": total_sales,
        "total_opening_stock": total_opening_stock,
        "total_parties": total_parties
    }

@api_router.delete("/transactions/all")
async def clear_all_transactions():
    """Clear all transactions"""
    result = await db.transactions.delete_many({})
    await db.opening_stock.delete_many({})
    return {"success": True, "deleted_count": result.deleted_count}

@api_router.get("/item/{item_name}")
async def get_item_detail(item_name: str):
    """Get detailed information about a specific item"""
    
    # Get all transactions for this item
    transactions = await db.transactions.find(
        {"item_name": item_name}, 
        {"_id": 0}
    ).sort("date", -1).to_list(1000)
    
    # Get opening stock
    opening = await db.opening_stock.find_one(
        {"item_name": item_name},
        {"_id": 0}
    )
    
    # Calculate statistics
    purchases = [t for t in transactions if t['type'] in ['purchase', 'purchase_return']]
    sales = [t for t in transactions if t['type'] in ['sale', 'sale_return']]
    
    total_purchase_wt = sum(t.get('net_wt', 0) for t in purchases if t['type'] == 'purchase')
    total_sale_wt = sum(t.get('net_wt', 0) for t in sales if t['type'] == 'sale')
    
    avg_purchase_tunch = (sum(float(t.get('tunch', 0) or 0) * t.get('net_wt', 0) for t in purchases) / total_purchase_wt) if total_purchase_wt > 0 else 0
    avg_sale_tunch = (sum(float(t.get('tunch', 0) or 0) * t.get('net_wt', 0) for t in sales) / total_sale_wt) if total_sale_wt > 0 else 0
    
    # Calculate current stock
    current_stock = (opening.get('net_wt', 0) if opening else 0) + total_purchase_wt - total_sale_wt
    
    # Get current stamp (latest from transactions or opening stock)
    current_stamp = None
    for t in transactions:
        if t.get('stamp'):
            current_stamp = t['stamp']
            break
    if not current_stamp and opening:
        current_stamp = opening.get('stamp')
    
    return {
        "item_name": item_name,
        "current_stamp": current_stamp or "Unassigned",
        "current_stock_kg": round(current_stock / 1000, 3),
        "total_purchases": len(purchases),
        "total_sales": len(sales),
        "avg_purchase_tunch": round(avg_purchase_tunch, 2),
        "avg_sale_tunch": round(avg_sale_tunch, 2),
        "tunch_margin": round(avg_sale_tunch - avg_purchase_tunch, 2),
        "recent_transactions": transactions[:20],
        "opening_stock": opening
    }

@api_router.post("/item/{item_name}/assign-stamp")
async def assign_stamp_to_item(item_name: str, stamp: str = Query(...)):
    """Assign stamp to all instances of an item"""
    
    # Update all transactions
    result1 = await db.transactions.update_many(
        {"item_name": item_name},
        {"$set": {"stamp": stamp}}
    )
    
    # Update opening stock
    result2 = await db.opening_stock.update_many(
        {"item_name": item_name},
        {"$set": {"stamp": stamp}}
    )
    
    await save_action('assign_stamp', f"Assigned stamp '{stamp}' to '{item_name}'")
    
    return {
        "success": True,
        "message": f"Stamp '{stamp}' assigned to '{item_name}'",
        "transactions_updated": result1.modified_count,
        "opening_stock_updated": result2.modified_count
    }

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
