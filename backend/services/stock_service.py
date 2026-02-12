from collections import defaultdict
from database import db


async def get_current_inventory():
    """Calculate current inventory: Opening Stock + Purchases - Sales.
    Merges item group members into their leader for consolidated view."""
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]

    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(10000)
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(10000)

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(10000)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in mappings}

    master_items = await db.master_items.find({}, {"_id": 0}).to_list(10000)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    # Load item groups for merging into leaders
    groups = await db.item_groups.find({}, {"_id": 0}).to_list(1000)
    member_to_leader = {}
    for g in groups:
        for member in g.get('members', []):
            if member != g['group_name']:
                member_to_leader[member] = g['group_name']

    opening = [item for item in opening if item['item_name'] not in EXCLUDED_ITEMS]
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS]

    inventory_map = {}

    for item in opening:
        key = item['item_name'].strip().lower()
        if key not in inventory_map:
            inventory_map[key] = {
                'item_name': item['item_name'],
                'stamp': item.get('stamp', '') or 'Unassigned',
                'stamp_locked': bool(item.get('stamp')),
                'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                'total_pc': 0, 'labor': 0.0, 'stamps_seen': set()
            }
        inventory_map[key]['gr_wt'] += item.get('gr_wt', 0)
        inventory_map[key]['net_wt'] += item.get('net_wt', 0)
        inventory_map[key]['fine'] += item.get('fine', 0)
        inventory_map[key]['total_pc'] += item.get('pc', 0)
        inventory_map[key]['labor'] += item.get('total', 0)
        if item.get('stamp'):
            inventory_map[key]['stamps_seen'].add(item['stamp'])
            inventory_map[key]['stamp'] = item['stamp']

    for trans in transactions:
        trans_name = trans['item_name'].strip()
        master_name = mapping_dict.get(trans_name, trans_name)
        key = master_name.strip().lower()

        if key not in inventory_map:
            item_stamp = master_stamp_dict.get(master_name, trans.get('stamp', 'Unassigned'))
            inventory_map[key] = {
                'item_name': master_name,
                'stamp': item_stamp,
                'stamp_locked': master_name in master_stamp_dict,
                'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                'total_pc': 0, 'labor': 0.0, 'stamps_seen': set()
            }

        if trans.get('stamp') and not inventory_map[key].get('stamp_locked', False):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])
            inventory_map[key]['stamp'] = trans['stamp']
        elif trans.get('stamp'):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])

        if trans['type'] in ['purchase', 'purchase_return', 'receive']:
            inventory_map[key]['gr_wt'] += trans.get('gr_wt', 0)
            inventory_map[key]['net_wt'] += trans.get('net_wt', 0)
            inventory_map[key]['fine'] += trans.get('fine', 0)
            inventory_map[key]['total_pc'] += trans.get('total_pc', 0)
            inventory_map[key]['labor'] += trans.get('labor', 0)
        else:
            inventory_map[key]['gr_wt'] -= trans.get('gr_wt', 0)
            inventory_map[key]['net_wt'] -= trans.get('net_wt', 0)
            inventory_map[key]['fine'] -= trans.get('fine', 0)
            inventory_map[key]['total_pc'] -= trans.get('total_pc', 0)
            inventory_map[key]['labor'] -= trans.get('labor', 0)

    inventory = []
    negative_items = []
    total_gr_wt = 0.0
    total_net_wt = 0.0

    ledger = await db.purchase_ledger.find({}, {"_id": 0}).to_list(10000)
    ledger_map = {item['item_name']: item for item in ledger}

    polythene_adjustments = await db.polythene_adjustments.find({}, {"_id": 0}).to_list(10000)
    poly_map = defaultdict(float)
    for adj in polythene_adjustments:
        adj_item_name = adj['item_name']
        master_item_name = mapping_dict.get(adj_item_name, adj_item_name)
        poly_weight = adj['poly_weight'] * 1000
        if adj['operation'] == 'add':
            poly_map[master_item_name] += poly_weight
        else:
            poly_map[master_item_name] -= poly_weight

    for key, item in inventory_map.items():
        item['stamps_seen'] = list(item['stamps_seen']) if isinstance(item['stamps_seen'], set) else item['stamps_seen']
        item_name = item['item_name']
        net_wt_grams = item['net_wt']

        ledger_item = ledger_map.get(item_name)
        if ledger_item:
            tunch = ledger_item.get('purchase_tunch', 0)
            labour_per_kg = ledger_item.get('labour_per_kg', 0)
            item['fine'] = (net_wt_grams * tunch / 100)
            item['labor'] = (net_wt_grams / 1000) * labour_per_kg

        if item_name in poly_map:
            item['gr_wt'] += poly_map[item_name]

        item['gr_wt'] = round(item['gr_wt'], 3)
        item['net_wt'] = round(item['net_wt'], 3)
        item['fine'] = round(item['fine'], 3)
        item['labor'] = round(item['labor'], 3)

        total_gr_wt += item['gr_wt']
        total_net_wt += item['net_wt']

        if item['gr_wt'] < -0.01 or item['net_wt'] < -0.01:
            negative_items.append(item)
        else:
            inventory.append(item)

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
        "total_gr_wt": round(total_gr_wt, 3),
        "total_net_wt": round(total_net_wt, 3),
        "negative_items": negative_items
    }
