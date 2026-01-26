from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
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
    type: str  # 'purchase' or 'sale'
    refno: Optional[str] = None
    party_name: Optional[str] = None
    item_name: str
    stamp: Optional[str] = None
    tag_no: Optional[str] = None
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine_sil: float = 0.0
    labor: float = 0.0
    dia_wt: float = 0.0
    stn_wt: float = 0.0
    total_pc: int = 0
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class PhysicalInventoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item_name: str
    stamp: Optional[str] = None
    gr_wt: float = 0.0
    poly_wt: float = 0.0
    net_wt: float = 0.0
    upload_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class BookInventoryItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_name: str
    stamp: Optional[str] = "Unassigned"
    gr_wt: float = 0.0
    net_wt: float = 0.0
    fine_sil: float = 0.0
    total_pc: int = 0

class InventorySnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    complete_match: bool = False
    differences: List[Dict[str, Any]] = []
    unmatched_items: List[Dict[str, Any]] = []

class ItemAnalytics(BaseModel):
    model_config = ConfigDict(extra="ignore")
    item_name: str
    stamp: Optional[str] = None
    movement_category: str  # 'fast', 'good', 'slow', 'dead'
    monthly_sale_kg: float = 0.0
    poly_ratio: Optional[float] = None
    is_exception: bool = False
    exception_reason: Optional[str] = None

class StampAssignment(BaseModel):
    item_name: str
    stamp: str

# Helper Functions
def parse_excel_file(file_content: bytes, file_type: str) -> List[Dict]:
    """Parse Excel file and return list of rows"""
    try:
        df = pd.read_excel(BytesIO(file_content))
        df = df.fillna('')
        
        if file_type == 'purchase':
            # Map columns based on purchase file structure
            records = []
            for _, row in df.iterrows():
                try:
                    record = {
                        'date': str(row.get('Date', '')),
                        'type': 'purchase',
                        'refno': str(row.get('Refno', '')),
                        'party_name': str(row.get('Party Name', '')),
                        'item_name': str(row.get('Item Name', '')),
                        'stamp': str(row.get('Stamp', '')),
                        'tag_no': str(row.get('Tag.No.', '')),
                        'gr_wt': float(row.get('Gr.Wt.', 0) or 0),
                        'net_wt': float(row.get('Net.Wt.', 0) or 0),
                        'fine_sil': float(row.get('Fine Sil.', 0) or 0),
                        'labor': float(row.get('Lbr. Wt/Rs', 0) or 0),
                        'dia_wt': float(row.get('Dia.Wt.', 0) or 0),
                        'stn_wt': float(row.get('Stn.Wt.', 0) or 0),
                        'total_pc': int(row.get('Total Pc', 0) or 0)
                    }
                    if record['item_name']:  # Only add if item name exists
                        records.append(record)
                except Exception as e:
                    continue
            return records
            
        elif file_type == 'sale':
            records = []
            for _, row in df.iterrows():
                try:
                    record = {
                        'type': 'sale',
                        'item_name': str(row.get('Item Name', row.get('Particular', ''))),
                        'gr_wt': float(row.get('Gr.Wt.', 0) or 0),
                        'net_wt': float(row.get('Less', 0) or 0),
                        'fine_sil': float(row.get('Fine Sil.', 0) or 0),
                        'labor': float(row.get('Fine Total', 0) or 0),
                        'dia_wt': float(row.get('Dia.Wt.', 0) or 0),
                        'stn_wt': float(row.get('Stn.Wt.', 0) or 0),
                        'total_pc': int(row.get('Pc', 0) or 0)
                    }
                    if record['item_name']:  # Only add if item name exists
                        records.append(record)
                except Exception as e:
                    continue
            return records
            
        elif file_type == 'physical':
            records = []
            for _, row in df.iterrows():
                try:
                    record = {
                        'item_name': str(row.get('Item Name', row.get('Particular', ''))),
                        'stamp': str(row.get('Stamp', '')),
                        'gr_wt': float(row.get('Gross Weight', row.get('Gr.Wt.', 0)) or 0),
                        'poly_wt': float(row.get('Poly Weight', 0) or 0),
                        'net_wt': float(row.get('Net Weight', row.get('Net.Wt.', 0)) or 0)
                    }
                    if record['item_name']:  # Only add if item name exists
                        records.append(record)
                except Exception as e:
                    continue
            return records
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing Excel file: {str(e)}")

@api_router.post("/transactions/upload/{file_type}")
async def upload_transaction_file(file_type: str, file: UploadFile = File(...)):
    """Upload purchase or sale Excel file"""
    if file_type not in ['purchase', 'sale']:
        raise HTTPException(status_code=400, detail="file_type must be 'purchase' or 'sale'")
    
    content = await file.read()
    records = parse_excel_file(content, file_type)
    
    if not records:
        raise HTTPException(status_code=400, detail="No valid records found in file")
    
    # Insert transactions
    transactions = [Transaction(**record).model_dump() for record in records]
    await db.transactions.insert_many(transactions)
    
    return {
        "success": True,
        "count": len(transactions),
        "message": f"{len(transactions)} {file_type} records uploaded successfully"
    }

@api_router.get("/transactions")
async def get_transactions(type: Optional[str] = None, limit: int = 1000):
    """Get all transactions"""
    query = {} if not type else {"type": type}
    transactions = await db.transactions.find(query, {"_id": 0}).to_list(limit)
    return transactions

@api_router.get("/inventory/book")
async def get_book_inventory():
    """Calculate and return current book inventory"""
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(10000)
    
    # Calculate inventory by item
    inventory_map = {}
    
    for trans in transactions:
        item_name = trans.get('item_name', '')
        if not item_name:
            continue
            
        if item_name not in inventory_map:
            inventory_map[item_name] = {
                'item_name': item_name,
                'stamp': trans.get('stamp', 'Unassigned'),
                'gr_wt': 0.0,
                'net_wt': 0.0,
                'fine_sil': 0.0,
                'total_pc': 0
            }
        
        if trans['type'] == 'purchase':
            inventory_map[item_name]['gr_wt'] += trans.get('gr_wt', 0)
            inventory_map[item_name]['net_wt'] += trans.get('net_wt', 0)
            inventory_map[item_name]['fine_sil'] += trans.get('fine_sil', 0)
            inventory_map[item_name]['total_pc'] += trans.get('total_pc', 0)
        else:  # sale
            inventory_map[item_name]['gr_wt'] -= trans.get('gr_wt', 0)
            inventory_map[item_name]['net_wt'] -= trans.get('net_wt', 0)
            inventory_map[item_name]['fine_sil'] -= trans.get('fine_sil', 0)
            inventory_map[item_name]['total_pc'] -= trans.get('total_pc', 0)
    
    inventory = list(inventory_map.values())
    
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
        "total_items": len(inventory)
    }

@api_router.post("/inventory/physical/upload")
async def upload_physical_inventory(file: UploadFile = File(...)):
    """Upload physical inventory Excel file"""
    content = await file.read()
    records = parse_excel_file(content, 'physical')
    
    if not records:
        raise HTTPException(status_code=400, detail="No valid records found in file")
    
    # Clear existing physical inventory
    await db.physical_inventory.delete_many({})
    
    # Insert new physical inventory
    physical_items = [PhysicalInventoryItem(**record).model_dump() for record in records]
    await db.physical_inventory.insert_many(physical_items)
    
    return {
        "success": True,
        "count": len(physical_items),
        "message": f"{len(physical_items)} physical inventory records uploaded successfully"
    }

@api_router.get("/inventory/physical")
async def get_physical_inventory():
    """Get current physical inventory"""
    physical = await db.physical_inventory.find({}, {"_id": 0}).to_list(10000)
    return physical

@api_router.post("/inventory/match")
async def match_inventory():
    """Match book inventory with physical inventory"""
    # Get book inventory
    book_response = await get_book_inventory()
    book_inventory = {item['item_name']: item for item in book_response['inventory']}
    
    # Get physical inventory
    physical_inventory = await db.physical_inventory.find({}, {"_id": 0}).to_list(10000)
    physical_map = {item['item_name']: item for item in physical_inventory}
    
    differences = []
    unmatched_physical = []
    matched_count = 0
    
    # Find differences in matched items
    for item_name, book_item in book_inventory.items():
        if item_name in physical_map:
            physical_item = physical_map[item_name]
            gr_wt_diff = physical_item['gr_wt'] - book_item['gr_wt']
            net_wt_diff = physical_item['net_wt'] - book_item['net_wt']
            
            if abs(gr_wt_diff) > 0.01 or abs(net_wt_diff) > 0.01:  # Allow small tolerance
                differences.append({
                    'item_name': item_name,
                    'stamp': book_item.get('stamp', 'Unassigned'),
                    'book_gr_wt': book_item['gr_wt'],
                    'physical_gr_wt': physical_item['gr_wt'],
                    'gr_wt_diff': gr_wt_diff,
                    'book_net_wt': book_item['net_wt'],
                    'physical_net_wt': physical_item['net_wt'],
                    'net_wt_diff': net_wt_diff
                })
            else:
                matched_count += 1
    
    # Find unmatched physical items
    for item_name, physical_item in physical_map.items():
        if item_name not in book_inventory:
            unmatched_physical.append(physical_item)
    
    complete_match = len(differences) == 0 and len(unmatched_physical) == 0
    
    # Save snapshot
    snapshot = InventorySnapshot(
        complete_match=complete_match,
        differences=differences,
        unmatched_items=unmatched_physical
    )
    await db.inventory_snapshots.insert_one(snapshot.model_dump())
    
    return {
        "complete_match": complete_match,
        "matched_count": matched_count,
        "differences": differences,
        "unmatched_items": unmatched_physical,
        "message": "Complete stock match!" if complete_match else f"Found {len(differences)} differences and {len(unmatched_physical)} unmatched items"
    }

@api_router.post("/inventory/assign-stamp")
async def assign_stamp(assignment: StampAssignment):
    """Assign stamp to an item in physical inventory"""
    result = await db.physical_inventory.update_one(
        {"item_name": assignment.item_name},
        {"$set": {"stamp": assignment.stamp}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    
    return {"success": True, "message": f"Stamp '{assignment.stamp}' assigned to '{assignment.item_name}'"}

@api_router.get("/analytics/movement")
async def get_movement_analytics():
    """Calculate item movement analytics"""
    # Get sales transactions from last 30 days
    sales = await db.transactions.find({"type": "sale"}, {"_id": 0}).to_list(10000)
    
    # Calculate monthly sales per item
    item_sales = {}
    for sale in sales:
        item_name = sale.get('item_name', '')
        if not item_name:
            continue
        if item_name not in item_sales:
            item_sales[item_name] = {'gr_wt': 0.0, 'stamp': sale.get('stamp', 'Unassigned')}
        item_sales[item_name]['gr_wt'] += sale.get('gr_wt', 0)
    
    # Categorize based on thresholds
    analytics = []
    for item_name, data in item_sales.items():
        monthly_kg = data['gr_wt'] / 1000  # Convert to kg
        
        if monthly_kg >= 150:
            category = 'fast'
        elif monthly_kg >= 50:
            category = 'good'
        elif monthly_kg >= 15:
            category = 'slow'
        else:
            category = 'dead'
        
        analytics.append({
            'item_name': item_name,
            'stamp': data['stamp'],
            'movement_category': category,
            'monthly_sale_kg': monthly_kg
        })
    
    return analytics

@api_router.get("/analytics/poly-exceptions")
async def get_poly_exceptions():
    """Identify items with skewed poly weight ratios"""
    physical = await db.physical_inventory.find({}, {"_id": 0}).to_list(10000)
    
    # Calculate ratios
    ratios = []
    for item in physical:
        if item['gr_wt'] > 0:
            ratio = (item['poly_wt'] / item['gr_wt']) * 100
            ratios.append({
                'item_name': item['item_name'],
                'stamp': item['stamp'],
                'gr_wt': item['gr_wt'],
                'poly_wt': item['poly_wt'],
                'poly_ratio': ratio
            })
    
    if not ratios:
        return []
    
    # Calculate average and standard deviation
    avg_ratio = sum(r['poly_ratio'] for r in ratios) / len(ratios)
    std_dev = (sum((r['poly_ratio'] - avg_ratio) ** 2 for r in ratios) / len(ratios)) ** 0.5
    
    # Mark exceptions (> 20% deviation from average)
    exceptions = []
    for item in ratios:
        deviation = abs(item['poly_ratio'] - avg_ratio)
        is_exception = deviation > (avg_ratio * 0.20)
        
        if is_exception:
            exceptions.append({
                **item,
                'is_exception': True,
                'exception_reason': f"Poly ratio {item['poly_ratio']:.2f}% deviates {deviation:.2f}% from average {avg_ratio:.2f}%"
            })
    
    return exceptions

@api_router.get("/snapshots")
async def get_snapshots(limit: int = 50):
    """Get inventory matching history"""
    snapshots = await db.inventory_snapshots.find({}, {"_id": 0}).sort("date", -1).to_list(limit)
    return snapshots

@api_router.get("/stats")
async def get_stats():
    """Get dashboard statistics"""
    total_transactions = await db.transactions.count_documents({})
    total_purchases = await db.transactions.count_documents({"type": "purchase"})
    total_sales = await db.transactions.count_documents({"type": "sale"})
    total_physical = await db.physical_inventory.count_documents({})
    
    # Get latest snapshot
    latest_snapshot = await db.inventory_snapshots.find_one(
        {},
        {"_id": 0},
        sort=[("date", -1)]
    )
    
    return {
        "total_transactions": total_transactions,
        "total_purchases": total_purchases,
        "total_sales": total_sales,
        "total_physical_items": total_physical,
        "latest_match": latest_snapshot
    }

@api_router.delete("/transactions/all")
async def clear_all_transactions():
    """Clear all transactions (for testing)"""
    result = await db.transactions.delete_many({})
    return {"success": True, "deleted_count": result.deleted_count}

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