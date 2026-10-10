from collections import defaultdict
from database import db
from services.group_utils import build_group_maps, build_group_ledger


async def get_book_closing_stock_as_of_date(verification_date: str):
    """Compute the closing/book stock as of a specific date.

    Logic: Opening Stock + Purchases(<=date) - Sales(<=date) +/- branch transfers(<=date)
    If an item has a physical stock baseline (baseline_date <= verification_date),
    uses: Baseline + transactions between baseline_date and verification_date.

    IMPORTANT: Computes at INDIVIDUAL item level. Groups are NOT merged.
    Each item retains its own stamp assignment.

    Returns a flat dict keyed by normalized item name:
      { "item_key": { item_name, stamp, gr_wt, net_wt, is_negative_grouped } }
    """
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]

    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(None)
    end_date = verification_date
    transactions = await db.transactions.find(
        {'date': {'$lte': end_date}}, {"_id": 0}
    ).to_list(None)

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(None)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    groups = await db.item_groups.find({}, {"_id": 0}).to_list(1000)

    baselines_raw = await db.inventory_baselines.find({}, {"_id": 0}).to_list(None)
    baselines = {b['item_key']: b for b in baselines_raw}

    mapping_dict, member_to_leader, group_members_map = build_group_maps(groups, mappings)

    group_names_set = {g['group_name'] for g in groups}

    opening = [i for i in opening if i['item_name'] not in EXCLUDED_ITEMS and not i['item_name'].isdigit()]
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS and not t['item_name'].isdigit()]

    def _resolve(raw_name):
        """Resolve transaction name to master name only. NO group merging."""
        master_name = mapping_dict.get(raw_name, raw_name)
        return master_name

    # Build baseline lookup at INDIVIDUAL item level (not leader level)
    baseline_by_key = {}
    for bval in baselines.values():
        raw = bval['item_name'].strip()
        master = mapping_dict.get(raw, raw)
        display_key = master.strip().lower()
        if bval['baseline_date'] <= verification_date:
            if display_key not in baseline_by_key or bval['baseline_date'] > baseline_by_key[display_key]['baseline_date']:
                baseline_by_key[display_key] = bval
    # Also index by raw item_key for direct match
    for bval in baselines.values():
        raw_key = bval['item_key']
        if raw_key not in baseline_by_key and bval['baseline_date'] <= verification_date:
            baseline_by_key[raw_key] = bval

    inventory_map = {}

    # Opening stock
    for item in opening:
        raw_name = item['item_name'].strip()
        display_name = _resolve(raw_name)
        key = display_name.strip().lower()
        if key in baseline_by_key:
            if key not in inventory_map:
                resolved_stamp = master_stamp_dict.get(
                    display_name, item.get('stamp', '') or 'Unassigned'
                )
                inventory_map[key] = {
                    'item_name': display_name, 'stamp': resolved_stamp,
                    'gr_wt': 0.0, 'net_wt': 0.0,
                }
            continue
        if key not in inventory_map:
            resolved_stamp = master_stamp_dict.get(
                display_name, item.get('stamp', '') or 'Unassigned'
            )
            inventory_map[key] = {
                'item_name': display_name, 'stamp': resolved_stamp,
                'gr_wt': 0.0, 'net_wt': 0.0,
            }
        inventory_map[key]['gr_wt'] += item.get('gr_wt', 0)
        inventory_map[key]['net_wt'] += item.get('net_wt', 0)

    # Inject baseline values
    for key, bl in baseline_by_key.items():
        if key not in inventory_map:
            bl_stamp = bl.get('stamp') or master_stamp_dict.get(bl['item_name'], 'Unassigned')
            inventory_map[key] = {
                'item_name': bl['item_name'], 'stamp': bl_stamp,
                'gr_wt': 0.0, 'net_wt': 0.0,
            }
        inventory_map[key]['gr_wt'] += bl['gr_wt']
        inventory_map[key]['net_wt'] += bl['net_wt']

    # Transactions
    for trans in transactions:
        trans_name = trans['item_name'].strip()
        display_name = _resolve(trans_name)
        key = display_name.strip().lower()
        bl = baseline_by_key.get(key)
        if bl and trans.get('date', '') <= bl['baseline_date']:
            continue
        if key not in inventory_map:
            item_stamp = master_stamp_dict.get(
                display_name, trans.get('stamp', 'Unassigned')
            )
            inventory_map[key] = {
                'item_name': display_name, 'stamp': item_stamp,
                'gr_wt': 0.0, 'net_wt': 0.0,
            }
        if trans['type'] in ['purchase', 'purchase_return', 'receive']:
            inventory_map[key]['gr_wt'] += trans.get('gr_wt', 0)
            inventory_map[key]['net_wt'] += trans.get('net_wt', 0)
        else:
            inventory_map[key]['gr_wt'] -= trans.get('gr_wt', 0)
            inventory_map[key]['net_wt'] -= trans.get('net_wt', 0)

    # Polythene adjustments
    polythene = await db.polythene_adjustments.find(
        {'date': {'$lte': end_date}}, {"_id": 0}
    ).to_list(None)
    poly_map = defaultdict(float)
    for adj in polythene:
        adj_item = adj['item_name']
        master_item = mapping_dict.get(adj_item, adj_item)
        adj_key = master_item.strip().lower()
        bl = baseline_by_key.get(adj_key)
        if bl and adj.get('date', '') <= bl['baseline_date']:
            continue
        pw = adj['poly_weight'] * 1000
        if adj['operation'] == 'add':
            poly_map[master_item] += pw
        else:
            poly_map[master_item] -= pw

    # Build result
    result = {}
    for key, item in inventory_map.items():
        item_name = item['item_name']
        if item_name in poly_map:
            item['gr_wt'] += poly_map[item_name]
        item['gr_wt'] = round(item['gr_wt'], 3)
        item['net_wt'] = round(item['net_wt'], 3)
        is_neg = item['gr_wt'] < -0.01 or item['net_wt'] < -0.01
        is_group = item_name in group_names_set
        result[key] = {
            'item_name': item_name,
            'stamp': item.get('stamp', 'Unassigned'),
            'gr_wt': item['gr_wt'],
            'net_wt': item['net_wt'],
            'is_negative_grouped': is_neg or is_group,
        }

    return result


async def get_effective_physical_base_for_date(verification_date: str):
    """Return the effective base stock for a physical stock update.

    If an active (non-reversed) session exists for the date, use the physical_stock snapshot.
    Otherwise, use get_current_inventory() to ensure the base matches what the
    Current Stock page shows (same identity model, polythene, grouping logic).

    Returns: dict keyed by normalized item name
      { "item_key": { item_name, stamp, gr_wt, net_wt, is_negative_grouped } }
    """
    active_session = await db.physical_stock_update_sessions.find_one({
        'verification_date': verification_date,
        'session_state': {'$in': ['finalized', 'draft']},
        'is_reversed': {'$ne': True},
        'applied_count': {'$gt': 0},
    })

    if active_session:
        existing = await db.physical_stock.find(
            {'verification_date': verification_date}, {"_id": 0}
        ).to_list(None)
        if existing:
            result = {}
            for doc in existing:
                key = doc['item_name'].strip().lower()
                result[key] = {
                    'item_name': doc['item_name'],
                    'stamp': doc.get('stamp', ''),
                    'gr_wt': doc.get('gr_wt', 0),
                    'net_wt': doc.get('net_wt', 0),
                    'is_negative_grouped': doc.get('is_negative_grouped', False),
                }
            return result

    return await _flat_base_from_inventory(verification_date)


async def _flat_base_from_inventory(as_of_date: str = None):
    """Build a flat base dict from get_current_inventory() output.
    Since items are now computed individually (not merged into groups),
    each item is already at the correct level for baselines.
    Returns: { "item_key": { item_name, stamp, gr_wt, net_wt, is_negative_grouped } }
    """
    current = await get_current_inventory(as_of_date=as_of_date)
    all_items = current.get('inventory', []) + current.get('negative_items', [])

    result = {}
    for item in all_items:
        item_name = item['item_name']
        # If this is a group display entry, use the members instead
        members = item.get('members', [])
        if item.get('is_group') and len(members) > 1:
            for member in members:
                m_key = member['item_name'].strip().lower()
                result[m_key] = {
                    'item_name': member['item_name'],
                    'stamp': member.get('stamp', 'Unassigned'),
                    'gr_wt': member.get('gr_wt', 0),
                    'net_wt': member.get('net_wt', 0),
                    'is_negative_grouped': True,
                }
        else:
            key = item_name.strip().lower()
            is_neg = item.get('gr_wt', 0) < -0.01 or item.get('net_wt', 0) < -0.01
            result[key] = {
                'item_name': item_name,
                'stamp': item.get('stamp', 'Unassigned'),
                'gr_wt': item.get('gr_wt', 0),
                'net_wt': item.get('net_wt', 0),
                'is_negative_grouped': is_neg,
            }
    return result


async def get_current_inventory(as_of_date: str = None):
    """Calculate current inventory: Opening Stock + Purchases - Sales.
    If an item has a physical stock baseline (from approved physical stock upload),
    that baseline replaces opening stock and only transactions AFTER the baseline date count.

    CRITICAL: Stock is computed at the INDIVIDUAL ITEM level.
    Groups are used ONLY for display purposes (expandable rows in Current Stock).
    Each item retains its own stamp assignment for stamp-level workflows.

    Args:
        as_of_date: Optional YYYY-MM-DD string. When set, only transactions and
                    polythene adjustments on or before this date are included, and
                    only baselines with baseline_date <= as_of_date are used.
    """
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]

    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(None)
    tx_filter = {'date': {'$lte': as_of_date}} if as_of_date else {}
    transactions = await db.transactions.find(tx_filter, {"_id": 0}).to_list(None)

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(None)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    groups = await db.item_groups.find({}, {"_id": 0}).to_list(1000)
    ledger_items = await db.purchase_ledger.find({}, {"_id": 0}).to_list(None)

    # Load inventory baselines (physical stock overrides)
    bl_filter = {'baseline_date': {'$lte': as_of_date}} if as_of_date else {}
    baselines_raw = await db.inventory_baselines.find(bl_filter, {"_id": 0}).to_list(None)
    baselines = {b['item_key']: b for b in baselines_raw}

    mapping_dict, member_to_leader, group_members = build_group_maps(groups, mappings)
    group_ledger = build_group_ledger(ledger_items, groups, mappings)

    opening = [item for item in opening if item['item_name'] not in EXCLUDED_ITEMS and not item['item_name'].isdigit()]
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS and not t['item_name'].isdigit()]

    def _resolve(raw_name):
        """Resolve transaction name to master name ONLY. NO group leader merging.
        Groups are for display/profit only, not stock computation."""
        master_name = mapping_dict.get(raw_name, raw_name)
        return master_name

    # Build baseline lookup at INDIVIDUAL item level (not group leader level)
    baseline_by_key = {}
    for bval in baselines.values():
        raw = bval['item_name'].strip()
        master = mapping_dict.get(raw, raw)
        # Key by the INDIVIDUAL master name, not the group leader
        display_key = master.strip().lower()
        if display_key not in baseline_by_key or bval['baseline_date'] > baseline_by_key[display_key]['baseline_date']:
            baseline_by_key[display_key] = bval
    # Also index by raw item_key for direct match
    for bval in baselines.values():
        raw_key = bval['item_key']
        if raw_key not in baseline_by_key:
            baseline_by_key[raw_key] = bval

    # Inventory map: keyed by INDIVIDUAL item (not group leader)
    inventory_map = {}

    # --- Opening stock ---
    for item in opening:
        raw_name = item['item_name'].strip()
        display_name = _resolve(raw_name)
        key = display_name.strip().lower()

        if key in baseline_by_key:
            if key not in inventory_map:
                resolved_stamp = master_stamp_dict.get(
                    display_name, item.get('stamp', '') or 'Unassigned'
                )
                inventory_map[key] = {
                    'item_name': display_name,
                    'stamp': resolved_stamp,
                    'stamp_locked': display_name in master_stamp_dict,
                    'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                    'total_pc': 0, 'labor': 0.0, 'stamps_seen': set()
                }
            if item.get('stamp'):
                inventory_map[key]['stamps_seen'].add(item['stamp'])
                if not inventory_map[key].get('stamp_locked', False):
                    inventory_map[key]['stamp'] = item['stamp']
            continue

        if key not in inventory_map:
            resolved_stamp = master_stamp_dict.get(
                display_name, item.get('stamp', '') or 'Unassigned'
            )
            inventory_map[key] = {
                'item_name': display_name,
                'stamp': resolved_stamp,
                'stamp_locked': display_name in master_stamp_dict,
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
            if not inventory_map[key].get('stamp_locked', False):
                inventory_map[key]['stamp'] = item['stamp']

    # --- Inject baseline values ---
    for key, bl in baseline_by_key.items():
        if key not in inventory_map:
            bl_stamp = bl.get('stamp') or master_stamp_dict.get(bl['item_name'], 'Unassigned')
            inventory_map[key] = {
                'item_name': bl['item_name'],
                'stamp': bl_stamp,
                'stamp_locked': bl['item_name'] in master_stamp_dict,
                'gr_wt': 0.0, 'net_wt': 0.0, 'fine': 0.0,
                'total_pc': 0, 'labor': 0.0, 'stamps_seen': set()
            }
        inventory_map[key]['gr_wt'] += bl['gr_wt']
        inventory_map[key]['net_wt'] += bl['net_wt']

    # --- Transactions ---
    for trans in transactions:
        trans_name = trans['item_name'].strip()
        display_name = _resolve(trans_name)
        key = display_name.strip().lower()

        bl = baseline_by_key.get(key)
        if bl and trans.get('date', '') <= bl['baseline_date']:
            continue

        if key not in inventory_map:
            item_stamp = master_stamp_dict.get(
                display_name, trans.get('stamp', 'Unassigned')
            )
            inventory_map[key] = {
                'item_name': display_name,
                'stamp': item_stamp,
                'stamp_locked': display_name in master_stamp_dict,
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

    # --- Polythene adjustments ---
    poly_filter = {'date': {'$lte': as_of_date}} if as_of_date else {}
    polythene_adjustments = await db.polythene_adjustments.find(poly_filter, {"_id": 0}).to_list(None)
    poly_map = defaultdict(float)
    for adj in polythene_adjustments:
        adj_item_name = adj['item_name']
        master_item_name = mapping_dict.get(adj_item_name, adj_item_name)
        adj_key = master_item_name.strip().lower()
        bl = baseline_by_key.get(adj_key)
        if bl and adj.get('date', '') <= bl['baseline_date']:
            continue
        poly_weight = adj['poly_weight'] * 1000
        if adj['operation'] == 'add':
            poly_map[master_item_name] += poly_weight
        else:
            poly_map[master_item_name] -= poly_weight

    # --- Build group membership lookup for display ---
    # Map: member_name -> group_name (for building display groups)
    item_to_group = {}
    group_members_list = {}
    for g in groups:
        gname = g['group_name']
        members = g.get('members', [])
        group_members_list[gname] = members
        for m in members:
            item_to_group[m] = gname

    # --- Build final inventory list ---
    # First pass: compute final values for each individual item
    all_computed = {}
    total_gr_wt = 0.0
    total_net_wt = 0.0

    for key, item in inventory_map.items():
        item['stamps_seen'] = list(item['stamps_seen']) if isinstance(item['stamps_seen'], set) else item['stamps_seen']
        item_name = item['item_name']
        net_wt_grams = item['net_wt']

        # Use GROUP-AWARE ledger for fine/labor calculation (groups DO affect profit)
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

        all_computed[item_name] = item

    # Second pass: build display list with group consolidation for Current Stock UI
    inventory = []
    negative_items = []
    grouped_items = set()  # Track items already included via a group

    # Build group display entries
    for gname, members in group_members_list.items():
        member_items = []
        for m_name in members:
            if m_name in all_computed:
                member_items.append(all_computed[m_name])
                grouped_items.add(m_name)

        if len(member_items) > 1:
            # Create a consolidated group display entry
            group_gr = sum(m['gr_wt'] for m in member_items)
            group_net = sum(m['net_wt'] for m in member_items)
            group_fine = sum(m.get('fine', 0) for m in member_items)
            group_labor = sum(m.get('labor', 0) for m in member_items)

            # Group stamp = the leader's stamp (for display header)
            leader_stamp = master_stamp_dict.get(gname, 'Unassigned')

            members_list = []
            for m_item in member_items:
                members_list.append({
                    'item_name': m_item['item_name'],
                    'stamp': m_item.get('stamp', 'Unassigned'),
                    'gr_wt': m_item['gr_wt'],
                    'net_wt': m_item['net_wt'],
                    'fine': m_item.get('fine', 0),
                    'labor': m_item.get('labor', 0),
                })
            members_list.sort(key=lambda x: x['net_wt'], reverse=True)

            group_entry = {
                'item_name': gname,
                'stamp': leader_stamp,
                'stamp_locked': gname in master_stamp_dict,
                'gr_wt': round(group_gr, 3),
                'net_wt': round(group_net, 3),
                'fine': round(group_fine, 3),
                'labor': round(group_labor, 3),
                'stamps_seen': [],
                'is_group': True,
                'members': members_list,
            }

            if group_gr < -0.01 or group_net < -0.01:
                negative_items.append(group_entry)
            else:
                inventory.append(group_entry)
        elif len(member_items) == 1:
            # Single member group — treat as individual
            pass  # Will be handled below as ungrouped

    # Add ungrouped items (not part of any multi-member group)
    for item_name, item in all_computed.items():
        if item_name in grouped_items:
            continue
        item['is_group'] = False
        item['members'] = []
        if item['gr_wt'] < -0.01 or item['net_wt'] < -0.01:
            negative_items.append(item)
        else:
            inventory.append(item)

    # --- by_stamp: each item goes to its OWN stamp (individual level) ---
    stamp_groups = {}
    stamp_items_flat = []

    for item_name, item in all_computed.items():
        stamp = item.get('stamp') or 'Unassigned'
        entry = {
            'item_name': item_name,
            'stamp': stamp,
            'gr_wt': item['gr_wt'],
            'net_wt': item['net_wt'],
            'fine': item.get('fine', 0),
            'labor': item.get('labor', 0),
        }
        stamp_groups.setdefault(stamp, []).append(entry)
        stamp_items_flat.append(entry)

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
    master_items = await db.master_items.find({'stamp': stamp}, {'_id': 0}).to_list(None)
    master_names = {m['item_name'] for m in master_items}

    all_master_items = await db.master_items.find({}, {'_id': 0, 'item_name': 1, 'stamp': 1}).to_list(None)
    all_master_names = {m['item_name'] for m in all_master_items}

    mappings = await db.item_mappings.find({}, {'_id': 0}).to_list(None)
    mapping_dict = {m['transaction_name']: m['master_name'] for m in mappings}

    reverse_map = defaultdict(set)
    for txn, master in mapping_dict.items():
        reverse_map[master].add(txn)

    groups = await db.item_groups.find({}, {'_id': 0}).to_list(1000)
    all_group_members = set()
    for g in groups:
        all_group_members.update(g.get('members', []))

    all_names_for_stamp = set(master_names)
    for name in master_names:
        for txn_name in reverse_map.get(name, set()):
            if txn_name not in all_master_names or txn_name in master_names:
                all_names_for_stamp.add(txn_name)

    opening = await db.opening_stock.find({}, {'_id': 0}).to_list(None)
    item_gross = defaultdict(float)

    for item in opening:
        raw_name = item['item_name'].strip()
        if raw_name in master_names:
            item_gross[raw_name] += item.get('gr_wt', 0)
        elif raw_name in all_names_for_stamp:
            resolved = mapping_dict.get(raw_name, raw_name)
            if resolved in master_names:
                physical = raw_name if raw_name in all_group_members else resolved
                if physical in master_names:
                    item_gross[physical] += item.get('gr_wt', 0)
                else:
                    item_gross[resolved] += item.get('gr_wt', 0)

    end_date = as_of_date + ' 23:59:59'
    transactions = await db.transactions.find(
        {'date': {'$lte': end_date}},
        {'_id': 0}
    ).to_list(None)

    for t in transactions:
        raw_name = t.get('item_name', '').strip()
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

    poly_end = as_of_date + ' 23:59:59'
    polythene = await db.polythene_adjustments.find(
        {'date': {'$lte': poly_end}},
        {'_id': 0}
    ).to_list(None)
    for adj in polythene:
        adj_name = adj['item_name']
        if adj_name in master_names:
            target = adj_name
        elif adj_name in all_names_for_stamp:
            resolved = mapping_dict.get(adj_name, adj_name)
            target = resolved if resolved in master_names else None
        else:
            target = None

        if not target:
            continue
        pw = adj['poly_weight'] * 1000
        if adj['operation'] == 'add':
            item_gross[target] += pw
        else:
            item_gross[target] -= pw

    return {name: round(gr / 1000, 3) for name, gr in item_gross.items()}
