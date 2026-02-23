from collections import defaultdict
from database import db
from services.group_utils import build_group_maps, build_group_ledger


async def get_current_inventory():
    """Calculate current inventory: Opening Stock + Purchases - Sales.
    Merges item group members into their leader for consolidated view.
    Returns per-member breakdowns for expandable UI."""
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]

    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(10000)
    transactions = await db.transactions.find({}, {"_id": 0}).to_list(10000)

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(10000)
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(10000)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    groups = await db.item_groups.find({}, {"_id": 0}).to_list(1000)
    ledger_items = await db.purchase_ledger.find({}, {"_id": 0}).to_list(10000)

    mapping_dict, member_to_leader, group_members = build_group_maps(groups, mappings)
    group_ledger = build_group_ledger(ledger_items, groups, mappings)

    opening = [item for item in opening if item['item_name'] not in EXCLUDED_ITEMS and not item['item_name'].isdigit()]
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS and not t['item_name'].isdigit()]

    # Track both group-level and per-member data
    inventory_map = {}
    member_data = defaultdict(lambda: defaultdict(lambda: {
        'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0, 'total_pc': 0, 'labor': 0.0
    }))

    # Set of all group member names — for preserving physical item identity
    all_group_members = set()
    for g in groups:
        all_group_members.update(g.get('members', []))

    def _resolve(raw_name):
        master_name = mapping_dict.get(raw_name, raw_name)
        leader = member_to_leader.get(master_name, master_name)
        return master_name, leader

    def _member_key(raw_name, master_name):
        """Determine which group member this item physically belongs to.
        If raw_name is itself a group member, keep it (preserves stamp identity).
        Otherwise fall back to master_name."""
        if raw_name in all_group_members:
            return raw_name
        return master_name

    # --- Opening stock ---
    for item in opening:
        raw_name = item['item_name'].strip()
        master_name, display_name = _resolve(raw_name)
        key = display_name.strip().lower()

        if key not in inventory_map:
            resolved_stamp = master_stamp_dict.get(
                display_name,
                master_stamp_dict.get(master_name, item.get('stamp', '') or 'Unassigned')
            )
            inventory_map[key] = {
                'item_name': display_name,
                'stamp': resolved_stamp,
                'stamp_locked': display_name in master_stamp_dict or master_name in master_stamp_dict,
                'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                'total_pc': 0, 'labor': 0.0, 'stamps_seen': set()
            }

        inventory_map[key]['gr_wt'] += item.get('gr_wt', 0)
        inventory_map[key]['net_wt'] += item.get('net_wt', 0)
        inventory_map[key]['fine'] += item.get('fine', 0)
        inventory_map[key]['total_pc'] += item.get('pc', 0)
        inventory_map[key]['labor'] += item.get('total', 0)

        # Track per-member data — preserve physical item identity
        m_key = _member_key(raw_name, master_name)
        member_data[key][m_key]['gr_wt'] += item.get('gr_wt', 0)
        member_data[key][m_key]['net_wt'] += item.get('net_wt', 0)
        member_data[key][m_key]['fine'] += item.get('fine', 0)
        member_data[key][m_key]['total_pc'] += item.get('pc', 0)
        member_data[key][m_key]['labor'] += item.get('total', 0)

        if item.get('stamp'):
            inventory_map[key]['stamps_seen'].add(item['stamp'])
            if not inventory_map[key].get('stamp_locked', False):
                inventory_map[key]['stamp'] = item['stamp']

    # --- Transactions ---
    for trans in transactions:
        trans_name = trans['item_name'].strip()
        master_name, display_name = _resolve(trans_name)
        key = display_name.strip().lower()

        if key not in inventory_map:
            item_stamp = master_stamp_dict.get(
                display_name,
                master_stamp_dict.get(master_name, trans.get('stamp', 'Unassigned'))
            )
            inventory_map[key] = {
                'item_name': display_name,
                'stamp': item_stamp,
                'stamp_locked': display_name in master_stamp_dict or master_name in master_stamp_dict,
                'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                'total_pc': 0, 'labor': 0.0, 'stamps_seen': set()
            }

        if trans.get('stamp') and not inventory_map[key].get('stamp_locked', False):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])
            inventory_map[key]['stamp'] = trans['stamp']
        elif trans.get('stamp'):
            inventory_map[key]['stamps_seen'].add(trans['stamp'])

        m_key = _member_key(trans_name, master_name)
        if trans['type'] in ['purchase', 'purchase_return', 'receive']:
            inventory_map[key]['gr_wt'] += trans.get('gr_wt', 0)
            inventory_map[key]['net_wt'] += trans.get('net_wt', 0)
            inventory_map[key]['fine'] += trans.get('fine', 0)
            inventory_map[key]['total_pc'] += trans.get('total_pc', 0)
            inventory_map[key]['labor'] += trans.get('labor', 0)

            member_data[key][m_key]['gr_wt'] += trans.get('gr_wt', 0)
            member_data[key][m_key]['net_wt'] += trans.get('net_wt', 0)
            member_data[key][m_key]['fine'] += trans.get('fine', 0)
            member_data[key][m_key]['total_pc'] += trans.get('total_pc', 0)
            member_data[key][m_key]['labor'] += trans.get('labor', 0)
        else:
            inventory_map[key]['gr_wt'] -= trans.get('gr_wt', 0)
            inventory_map[key]['net_wt'] -= trans.get('net_wt', 0)
            inventory_map[key]['fine'] -= trans.get('fine', 0)
            inventory_map[key]['total_pc'] -= trans.get('total_pc', 0)
            inventory_map[key]['labor'] -= trans.get('labor', 0)

            member_data[key][m_key]['gr_wt'] -= trans.get('gr_wt', 0)
            member_data[key][m_key]['net_wt'] -= trans.get('net_wt', 0)
            member_data[key][m_key]['fine'] -= trans.get('fine', 0)
            member_data[key][m_key]['total_pc'] -= trans.get('total_pc', 0)
            member_data[key][m_key]['labor'] -= trans.get('labor', 0)

    # --- Polythene adjustments ---
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

    # --- Build final inventory list ---
    group_names_set = {g['group_name'] for g in groups}
    inventory = []
    negative_items = []
    total_gr_wt = 0.0
    total_net_wt = 0.0

    for key, item in inventory_map.items():
        item['stamps_seen'] = list(item['stamps_seen']) if isinstance(item['stamps_seen'], set) else item['stamps_seen']
        item_name = item['item_name']
        net_wt_grams = item['net_wt']

        # Use GROUP-AWARE ledger for fine/labor calculation
        ledger_item = group_ledger.get(item_name)
        if ledger_item:
            tunch = ledger_item.get('purchase_tunch', 0)
            labour_per_kg = ledger_item.get('labour_per_kg', 0)
            item['fine'] = net_wt_grams * tunch / 100
            item['labor'] = (net_wt_grams / 1000) * labour_per_kg

        # Polythene adjustment
        if item_name in poly_map:
            item['gr_wt'] += poly_map[item_name]

        item['gr_wt'] = round(item['gr_wt'], 3)
        item['net_wt'] = round(item['net_wt'], 3)
        item['fine'] = round(item['fine'], 3)
        item['labor'] = round(item['labor'], 3)

        total_gr_wt += item['gr_wt']
        total_net_wt += item['net_wt']

        # Determine if this is a group and build member details
        is_group = item_name in group_names_set
        item['is_group'] = is_group

        if is_group and key in member_data and len(member_data[key]) > 1:
            members_list = []
            for m_name, m_vals in member_data[key].items():
                m_net = m_vals['net_wt']
                m_gr = m_vals['gr_wt']
                # Use group ledger for member fine/labor too
                if ledger_item:
                    m_fine = m_net * tunch / 100
                    m_labor = (m_net / 1000) * labour_per_kg
                else:
                    m_fine = m_vals['fine']
                    m_labor = m_vals['labor']
                m_stamp = master_stamp_dict.get(m_name, item.get('stamp', 'Unassigned'))
                members_list.append({
                    'item_name': m_name,
                    'stamp': m_stamp,
                    'gr_wt': round(m_gr, 3),
                    'net_wt': round(m_net, 3),
                    'fine': round(m_fine, 3),
                    'labor': round(m_labor, 3),
                })
            item['members'] = sorted(members_list, key=lambda x: x['net_wt'], reverse=True)
        else:
            item['members'] = []

        if item['gr_wt'] < -0.01 or item['net_wt'] < -0.01:
            negative_items.append(item)
        else:
            inventory.append(item)

    # --- by_stamp: distribute individual members to their own stamps ---
    # This is critical for stamp-level tallying (approvals, physical vs book)
    stamp_groups = {}
    stamp_items_flat = []  # flat list of per-stamp items for stamp detail/physical compare

    for item in inventory + negative_items:
        if item.get('is_group') and item.get('members') and len(item['members']) > 1:
            # Distribute each member to its own stamp
            for m in item['members']:
                m_stamp = m.get('stamp') or 'Unassigned'
                m_entry = {**m, 'group_name': item['item_name']}
                stamp_groups.setdefault(m_stamp, []).append(m_entry)
                stamp_items_flat.append(m_entry)
        else:
            stamp = item.get('stamp') or 'Unassigned'
            stamp_groups.setdefault(stamp, []).append(item)
            stamp_items_flat.append(item)

    return {
        "inventory": inventory,
        "by_stamp": stamp_groups,
        "stamp_items": stamp_items_flat,
        "total_items": len(inventory),
        "total_gr_wt": round(total_gr_wt, 3),
        "total_net_wt": round(total_net_wt, 3),
        "negative_items": negative_items
    }


async def get_stamp_closing_stock(stamp: str, as_of_date: str):
    """Calculate closing gross weight (in kg) for each item in a stamp as of a date.

    Logic: opening_stock + transactions(date <= as_of_date)
    Uses per-stamp item identity (not merged groups) so stamp tallies are correct.
    Returns: dict {item_name: gross_wt_kg}
    """
    # Load master items for this stamp
    master_items = await db.master_items.find({'stamp': stamp}, {'_id': 0}).to_list(10000)
    master_names = {m['item_name'] for m in master_items}

    # Load ALL master item names (any stamp) — to detect when a mapped name
    # is itself a master item in another stamp (should NOT be counted here)
    all_master_items = await db.master_items.find({}, {'_id': 0, 'item_name': 1, 'stamp': 1}).to_list(10000)
    all_master_names = {m['item_name'] for m in all_master_items}

    # Mappings: which transaction names resolve to items in this stamp
    mappings = await db.item_mappings.find({}, {'_id': 0}).to_list(10000)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in mappings}

    # Reverse: master_name -> set of transaction_names
    reverse_map = defaultdict(set)
    for txn, master in mapping_dict.items():
        reverse_map[master].add(txn)

    # Groups: for physical identity resolution
    groups = await db.item_groups.find({}, {'_id': 0}).to_list(1000)
    all_group_members = set()
    for g in groups:
        all_group_members.update(g.get('members', []))

    # Build set of ALL names that map to items in this stamp
    # EXCLUDE names that are themselves master items in OTHER stamps
    all_names_for_stamp = set(master_names)
    for name in master_names:
        for txn_name in reverse_map.get(name, set()):
            # Only include if txn_name is NOT a master item in another stamp
            if txn_name not in all_master_names or txn_name in master_names:
                all_names_for_stamp.add(txn_name)

    # 1. Opening stock
    opening = await db.opening_stock.find({}, {'_id': 0}).to_list(10000)
    item_gross = defaultdict(float)

    for item in opening:
        raw_name = item['item_name'].strip()
        # Direct match to this stamp's items
        if raw_name in master_names:
            item_gross[raw_name] += item.get('gr_wt', 0)
        elif raw_name in all_names_for_stamp:
            resolved = mapping_dict.get(raw_name, raw_name)
            if resolved in master_names:
                # But preserve physical identity if it's a group member
                physical = raw_name if raw_name in all_group_members else resolved
                if physical in master_names:
                    item_gross[physical] += item.get('gr_wt', 0)
                else:
                    item_gross[resolved] += item.get('gr_wt', 0)

    # 2. Transactions up to and including as_of_date
    end_date = as_of_date + ' 23:59:59'
    transactions = await db.transactions.find(
        {'date': {'$lte': end_date}},
        {'_id': 0}
    ).to_list(100000)

    for t in transactions:
        raw_name = t.get('item_name', '').strip()
        # Determine which stamp item this belongs to
        target = None
        if raw_name in master_names:
            target = raw_name
        elif raw_name in all_names_for_stamp:
            resolved = mapping_dict.get(raw_name, raw_name)
            physical = raw_name if raw_name in all_group_members and raw_name in master_names else resolved
            if physical in master_names:
                target = physical
            elif resolved in master_names:
                target = resolved

        if not target:
            continue

        gr = t.get('gr_wt', 0)
        if t['type'] in ['purchase', 'purchase_return', 'receive']:
            item_gross[target] += gr
        else:
            item_gross[target] -= gr

    # Polythene adjustments — date-filtered up to as_of_date
    poly_end = as_of_date + ' 23:59:59'
    polythene = await db.polythene_adjustments.find(
        {'date': {'$lte': poly_end}},
        {'_id': 0}
    ).to_list(10000)
    for adj in polythene:
        adj_name = adj['item_name']
        # Direct match to this stamp's items
        if adj_name in master_names:
            target = adj_name
        elif adj_name in all_names_for_stamp:
            resolved = mapping_dict.get(adj_name, adj_name)
            target = resolved if resolved in master_names else None
        else:
            target = None

        if not target:
            continue
        pw = adj['poly_weight'] * 1000  # kg to grams
        if adj['operation'] == 'add':
            item_gross[target] += pw
        else:
            item_gross[target] -= pw

    # Convert to kg and return
    return {name: round(gr / 1000, 3) for name, gr in item_gross.items()}

