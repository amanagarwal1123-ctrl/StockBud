import re
import pandas as pd
from datetime import datetime, timezone
from database import db
from models import ActionHistory


def normalize_stamp(stamp_value):
    """Normalize stamp to consistent 'STAMP X' format (ALL CAPS)"""
    if not stamp_value or pd.isna(stamp_value):
        return 'Unassigned'
    stamp_str = str(stamp_value).strip()
    if not stamp_str or stamp_str.lower() == 'unassigned':
        return 'Unassigned'
    match = re.search(r'(\d+)', stamp_str)
    if match:
        return f'STAMP {match.group(1)}'
    return 'Unassigned'


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


def normalize_date(date_value):
    """Normalize date to YYYY-MM-DD format"""
    if not date_value or pd.isna(date_value):
        return ''
    date_str = str(date_value).strip()
    if ' ' in date_str:
        date_str = date_str.split(' ')[0]
    try:
        dt = pd.to_datetime(date_str)
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str


def stamp_sort_key(s):
    """Safe numeric sort key for stamps like 'STAMP 7', 'Stamp 12'"""
    match = re.search(r'(\d+)', s or '')
    return int(match.group(1)) if match else 0


async def save_action(action_type: str, description: str, data_snapshot: dict = None, user: dict = None):
    """Save action for undo/redo and accountability"""
    action = ActionHistory(
        action_type=action_type,
        description=description,
        data_snapshot=data_snapshot or {}
    )
    await db.action_history.insert_one(action.model_dump())

    if user:
        await db.activity_log.insert_one({
            'user': user.get('username', 'system'),
            'user_role': user.get('role', 'system'),
            'action_type': action_type,
            'description': description,
            'details': data_snapshot or {},
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    count = await db.action_history.count_documents({})
    if count > 20:
        oldest = await db.action_history.find({}, {"_id": 1}).sort("timestamp", 1).limit(count - 20).to_list(count)
        if oldest:
            await db.action_history.delete_many({"_id": {"$in": [doc["_id"] for doc in oldest]}})


async def auto_normalize_stamps():
    """Auto-normalize stamps across all collections after upload"""
    all_stamps = set()
    all_stamps.update(await db.master_items.distinct('stamp'))
    all_stamps.update(await db.transactions.distinct('stamp'))
    all_stamps.update(await db.opening_stock.distinct('stamp'))

    stamp_mapping = {}
    for stamp in all_stamps:
        if not stamp or stamp == 'Unassigned':
            continue
        match = re.search(r'(\d+)', stamp)
        if match:
            normalized = f'STAMP {match.group(1)}'
            if stamp != normalized:
                stamp_mapping[stamp] = normalized
    if '' in all_stamps:
        stamp_mapping[''] = 'Unassigned'

    if not stamp_mapping:
        return 0

    total_updated = 0
    collections_to_update = [
        'master_items', 'transactions', 'opening_stock', 'stock_entries',
        'stamp_approvals', 'stamp_verifications', 'physical_inventory'
    ]
    for old_stamp, new_stamp in stamp_mapping.items():
        for coll_name in collections_to_update:
            result = await db[coll_name].update_many(
                {'stamp': old_stamp},
                {'$set': {'stamp': new_stamp}}
            )
            total_updated += result.modified_count

    return total_updated
