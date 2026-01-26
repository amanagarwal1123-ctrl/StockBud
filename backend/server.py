from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Query, Query
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import pandas as pd
import openpyxl
from io import BytesIO
import json
from collections import defaultdict

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# Models
class Transaction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
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
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

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

# Save action for undo/redo
async def save_action(action_type: str, description: str, data_snapshot: dict = None):
    action = ActionHistory(
        action_type=action_type,
        description=description,
        data_snapshot=data_snapshot or {}
    )
    await db.action_history.insert_one(action.model_dump())
    
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

@api_router.post("/transactions/upload/{file_type}")
async def upload_transaction_file(file_type: str, file: UploadFile = File(...)):
    """Upload purchase or sale Excel file"""
    if file_type not in ['purchase', 'sale']:
        raise HTTPException(status_code=400, detail="file_type must be 'purchase' or 'sale'")
    
    content = await file.read()
    records = parse_excel_file(content, file_type)
    
    if not records:
        raise HTTPException(status_code=400, detail="No valid records found in file")
    
    transactions = [Transaction(**record).model_dump() for record in records]
    result = await db.transactions.insert_many(transactions)
    
    await save_action(f'upload_{file_type}', f"Uploaded {len(transactions)} {file_type} transactions")
    
    return {
        "success": True,
        "count": len(transactions),
        "message": f"{len(transactions)} {file_type} records uploaded successfully"
    }

@api_router.get("/transactions")
async def get_transactions(type: Optional[str] = None, limit: int = 5000):
    """Get all transactions"""
    query = {} if not type else {"type": type}
    transactions = await db.transactions.find(query, {"_id": 0}).sort("date", -1).to_list(limit)
    return transactions

@api_router.get("/inventory/current")
async def get_current_inventory():
    """Calculate current inventory: Opening Stock + Purchases - Sales"""
    
    # Get opening stock and transactions
    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(10000)
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(10000)
    
    # Build inventory map starting with opening stock
    inventory_map = {}
    
    # Add all opening stock items
    for item in opening:
        key = item['item_name'].strip().lower()
        if key not in inventory_map:
            inventory_map[key] = {
                'item_name': item['item_name'],
                'stamp': item.get('stamp', '') or 'Unassigned',
                'gr_wt': 0.0,
                'net_wt': 0.0,
                'fine': 0.0,
                'total_pc': 0,
                'stamps_seen': set()
            }
        inventory_map[key]['gr_wt'] += item.get('gr_wt', 0)
        inventory_map[key]['net_wt'] += item.get('net_wt', 0)
        inventory_map[key]['fine'] += item.get('fine', 0)
        inventory_map[key]['total_pc'] += item.get('pc', 0)
        if item.get('stamp'):
            inventory_map[key]['stamps_seen'].add(item['stamp'])
    
    # Process all transactions
    for trans in transactions:
        key = trans['item_name'].strip().lower()
        if key not in inventory_map:
            inventory_map[key] = {
                'item_name': trans['item_name'],
                'stamp': trans.get('stamp', 'Unassigned'),
                'gr_wt': 0.0,
                'net_wt': 0.0,
                'fine': 0.0,
                'total_pc': 0,
                'stamps_seen': set()
            }
        
        if trans.get('stamp'):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])
            inventory_map[key]['stamp'] = trans['stamp']
        
        # Weights in Excel already include negatives for returns
        # Purchase types (P, PR): ADD to stock
        # Sale types (S, SR): SUBTRACT from stock
        multiplier = 1 if trans['type'] in ['purchase', 'purchase_return'] else -1
        
        inventory_map[key]['gr_wt'] += trans.get('gr_wt', 0) * multiplier
        inventory_map[key]['net_wt'] += trans.get('net_wt', 0) * multiplier
        inventory_map[key]['fine'] += trans.get('fine', 0) * multiplier
        inventory_map[key]['total_pc'] += trans.get('total_pc', 0) * multiplier
    
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
async def upload_physical_stock(file: UploadFile = File(...)):
    """Upload physical stock file and merge items by name"""
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
                    'fine': 0.0
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
            "message": f"Physical stock uploaded: {len(stock_items)} items, {total_net_wt/1000:.3f} kg"
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

@api_router.get("/analytics/party-analysis")
async def get_party_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Analyze parties (customers and suppliers) with silver weight comparisons"""
    
    query = {}
    if start_date and end_date:
        query['date'] = {'$gte': start_date, '$lte': end_date}
    
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

@api_router.get("/analytics/profit")
async def calculate_profit(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Calculate profit: Silver profit (in kg) and Labour profit (in INR)"""
    
    query = {}
    if start_date and end_date:
        query['date'] = {'$gte': start_date, '$lte': end_date}
    
    transactions = await db.transactions.find(query, {"_id": 0}).to_list(10000)
    
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
        
        if not purchases or not sales:
            continue
        
        # Calculate total and average values
        total_purchase_wt = sum(p['net_wt'] for p in purchases)
        total_sale_wt = sum(s['net_wt'] for s in sales)
        
        if abs(total_purchase_wt) < 0.001 or abs(total_sale_wt) < 0.001:
            continue
        
        # Average tunch weighted by ABSOLUTE net weight (to handle negative returns correctly)
        avg_purchase_tunch = sum(p['tunch'] * abs(p['net_wt']) for p in purchases) / sum(abs(p['net_wt']) for p in purchases) if purchases else 0
        avg_sale_tunch = sum(s['tunch'] * abs(s['net_wt']) for s in sales) / sum(abs(s['net_wt']) for s in sales) if sales else 0
        
        # Labour per kg = Total labour / Net weight (using absolute values for average)
        avg_purchase_labor_per_kg = sum(abs(p['labor']) for p in purchases) / sum(abs(p['net_wt']) for p in purchases) if purchases else 0
        avg_sale_labor_per_kg = sum(abs(s['labor']) for s in sales) / sum(abs(s['net_wt']) for s in sales) if sales else 0
        
        # USER'S FORMULA:
        # 1. Silver Profit (kg) = (sale tunch - purchase tunch) * sale net weight / 100
        silver_profit_grams = (avg_sale_tunch - avg_purchase_tunch) * total_sale_wt / 100
        silver_profit_kg = silver_profit_grams / 1000  # Convert to kg
        
        # 2. Labour Profit (INR) = (sale labour per kg - purchase labour per kg) * sale net weight
        labor_profit_inr = (avg_sale_labor_per_kg - avg_purchase_labor_per_kg) * total_sale_wt
        
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
        "current_stock_kg": round(current_stock, 3),
        "total_purchases": len(purchases),
        "total_sales": len(sales),
        "avg_purchase_tunch": round(avg_purchase_tunch, 2),
        "avg_sale_tunch": round(avg_sale_tunch, 2),
        "tunch_margin": round(avg_sale_tunch - avg_purchase_tunch, 2),
        "recent_transactions": transactions[:20],
        "opening_stock": opening
    }

@api_router.post("/item/{item_name}/assign-stamp")
async def assign_stamp_to_item(item_name: str, stamp: str):
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
