from collections import defaultdict
from database import db
from services.group_utils import build_group_maps, build_group_ledger


async def get_book_closing_stock_as_of_date(verification_date: str):
    """Compute the closing/book stock as of a specific date.

    Logic: Opening Stock + Purchases(<=date) - Sales(<=date) +/- branch transfers(<=date)
    If an item has a physical stock baseline (baseline_date <= verification_date),
    uses: Baseline + transactions between baseline_date and verification_date.
    Same mapping/grouping logic as get_current_inventory() but date-filtered.

    Returns a flat dict keyed by normalized item name:
      { "item_key": { item_name, stamp, gr_wt, net_wt, is_negative_grouped } }
    """
    EXCLUDED_ITEMS = ["SILVER ORNAMENTS"]

    opening = await db.opening_stock.find({}, {"_id": 0}).to_list(None)
    # Filter transactions up to and including the verification_date
    end_date = verification_date  # YYYY-MM-DD string comparison works
    transactions = await db.transactions.find(
        {'date': {'$lte': end_date}}, {"_id": 0}
    ).to_list(None)

    mappings = await db.item_mappings.find({}, {"_id": 0}).to_list(None)
    master_items = await db.master_items.find({}, {"_id": 0}).to_list(None)
    master_stamp_dict = {m['item_name']: m['stamp'] for m in master_items}

    groups = await db.item_groups.find({}, {"_id": 0}).to_list(1000)

    # Load inventory baselines
    baselines_raw = await db.inventory_baselines.find({}, {"_id": 0}).to_list(None)
    baselines = {b['item_key']: b for b in baselines_raw}

    mapping_dict, member_to_leader, group_members_map = build_group_maps(groups, mappings)

    group_names_set = {g['group_name'] for g in groups}
    all_group_members = set()
    for g in groups:
        all_group_members.update(g.get('members', []))

    opening = [i for i in opening if i['item_name'] not in EXCLUDED_ITEMS and not i['item_name'].isdigit()]
    transactions = [t for t in transactions if t['item_name'] not in EXCLUDED_ITEMS and not t['item_name'].isdigit()]

    def _resolve(raw_name):
        master_name = mapping_dict.get(raw_name, raw_name)
        leader = member_to_leader.get(master_name, master_name)
        return master_name, leader

    # Build baseline lookup by resolved display key
    baseline_by_key = {}
    for bval in baselines.values():
        raw = bval['item_name'].strip()
        master = mapping_dict.get(raw, raw)
        leader = member_to_leader.get(master, master)
        display_key = leader.strip().lower()
        # Only use baseline if baseline_date <= verification_date
        if bval['baseline_date'] <= verification_date:
            if display_key not in baseline_by_key or bval['baseline_date'] > baseline_by_key[display_key]['baseline_date']:
                baseline_by_key[display_key] = bval
    for bval in baselines.values():
        raw_key = bval['item_key']
        if raw_key not in baseline_by_key and bval['baseline_date'] <= verification_date:
            baseline_by_key[raw_key] = bval

    inventory_map = {}

    # Opening stock — skip items with baselines
    for item in opening:
        raw_name = item['item_name'].strip()
        master_name, display_name = _resolve(raw_name)
        key = display_name.strip().lower()
        if key in baseline_by_key:
            # Initialize entry but skip opening values
            if key not in inventory_map:
                resolved_stamp = master_stamp_dict.get(
                    display_name,
                    master_stamp_dict.get(master_name, item.get('stamp', '') or 'Unassigned')
                )
                inventory_map[key] = {
                    'item_name': display_name, 'stamp': resolved_stamp,
                    'gr_wt': 0.0, 'net_wt': 0.0,
                }
            continue
        if key not in inventory_map:
            resolved_stamp = master_stamp_dict.get(
                display_name,
                master_stamp_dict.get(master_name, item.get('stamp', '') or 'Unassigned')
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

    # Transactions — skip pre-baseline transactions for baseline items
    for trans in transactions:
        trans_name = trans['item_name'].strip()
        master_name, display_name = _resolve(trans_name)
        key = display_name.strip().lower()
        bl = baseline_by_key.get(key)
        if bl and trans.get('date', '') <= bl['baseline_date']:
            continue  # Already accounted for in baseline
        if key not in inventory_map:
            item_stamp = master_stamp_dict.get(
                display_name,
                master_stamp_dict.get(master_name, trans.get('stamp', 'Unassigned'))
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

    # Polythene adjustments up to date — skip pre-baseline for baseline items
    polythene = await db.polythene_adjustments.find(
        {'date': {'$lte': end_date}}, {"_id": 0}
    ).to_list(None)
    poly_map = defaultdict(float)
    for adj in polythene:
        adj_item = adj['item_name']
        master_item = mapping_dict.get(adj_item, adj_item)
        leader = member_to_leader.get(master_item, master_item)
        adj_key = leader.strip().lower()
        bl = baseline_by_key.get(adj_key)
        if bl and adj.get('date', '') <= bl['baseline_date']:
            continue
        pw = adj['poly_weight'] * 1000
        if adj['operation'] == 'add':
            poly_map[leader] += pw
        else:
            poly_map[leader] -= pw

    # Build result — tag negative/grouped items
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
    # Check if there's any active (non-reversed, applied) session for this date
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

    # Use current inventory computation with date filtering to ensure base matches
    # the Current Stock page identity model (polythene keying, group handling).
    return await _flat_base_from_inventory(verification_date)


async def _flat_base_from_inventory(as_of_date: str = None):
    """Build a flat base dict from get_current_inventory() output.
    For groups with 2+ members, returns MEMBER-level entries (not leader-level).
    This ensures baselines are created at the member level during apply-updates,
    preventing negative stock for group members after reconciliation.
    Returns: { "item_key": { item_name, stamp, gr_wt, net_wt, is_negative_grouped } }
    """
    current = await get_current_inventory(as_of_date=as_of_date)
    all_items = current.get('inventory', []) + current.get('negative_items', [])

    groups_raw = await db.item_groups.find({}, {"_id": 0}).to_list(1000)
    group_names_set = {g['group_name'] for g in groups_raw}

    result = {}
    for item in all_items:
        item_name = item['item_name']
        is_group = item_name in group_names_set
        members = item.get('members', [])

        if is_group and len(members) > 1:
            # Decompose group into member-level entries so each member
            # gets its own baseline when physical stock is approved.
            for member in members:
                m_key = member['item_name'].strip().lower()
                m_is_neg = member.get('gr_wt', 0) < -0.01 or member.get('net_wt', 0) < -0.01
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
                'is_negative_grouped': is_neg or is_group,
            }
    return result


async def get_current_inventory(as_of_date: str = None):
    """Calculate current inventory: Opening Stock + Purchases - Sales.
    If an item has a physical stock baseline (from approved physical stock upload),
    that baseline replaces opening stock and only transactions AFTER the baseline date count.
    Merges item group members into their leader for consolidated view.
    Returns per-member breakdowns for expandable UI.

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

    # Build baseline lookup keyed by resolved display name
    baseline_by_key = {}
    for bval in baselines.values():
        raw = bval['item_name'].strip()
        master = mapping_dict.get(raw, raw)
        leader = member_to_leader.get(master, master)
        display_key = leader.strip().lower()
        # Keep the latest baseline if multiple resolve to the same display key
        if display_key not in baseline_by_key or bval['baseline_date'] > baseline_by_key[display_key]['baseline_date']:
            baseline_by_key[display_key] = bval
    # Also index by raw item_key for direct match
    for bval in baselines.values():
        raw_key = bval['item_key']
        if raw_key not in baseline_by_key:
            baseline_by_key[raw_key] = bval

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

        # If this item has a physical stock baseline, skip opening stock
        if key in baseline_by_key:
            # Still need to initialize inventory_map entry for stamp/metadata
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
            if item.get('stamp'):
                inventory_map[key]['stamps_seen'].add(item['stamp'])
                if not inventory_map[key].get('stamp_locked', False):
                    inventory_map[key]['stamp'] = item['stamp']
            continue  # Skip opening values — baseline will be applied below

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

    # --- Inject baseline values as the new starting point for baseline items ---
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
        m_key = _member_key(bl['item_name'], bl['item_name'])
        member_data[key][m_key]['gr_wt'] += bl['gr_wt']
        member_data[key][m_key]['net_wt'] += bl['net_wt']

    # --- Transactions ---
    for trans in transactions:
        trans_name = trans['item_name'].strip()
        master_name, display_name = _resolve(trans_name)
        key = display_name.strip().lower()

        # If this item has a baseline, skip transactions on or before baseline date
        bl = baseline_by_key.get(key)
        if bl and trans.get('date', '') <= bl['baseline_date']:
            continue  # Transaction is before/on baseline — already accounted for

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
    poly_filter = {'date': {'$lte': as_of_date}} if as_of_date else {}
    polythene_adjustments = await db.polythene_adjustments.find(poly_filter, {"_id": 0}).to_list(None)
    poly_map = defaultdict(float)
    for adj in polythene_adjustments:
        adj_item_name = adj['item_name']
        master_item_name = mapping_dict.get(adj_item_name, adj_item_name)
        leader = member_to_leader.get(master_item_name, master_item_name)
        adj_key = leader.strip().lower()
        # Skip polythene adjustments on or before baseline date for baseline items
        bl = baseline_by_key.get(adj_key)
        if bl and adj.get('date', '') <= bl['baseline_date']:
            continue
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
    master_items = await db.master_items.find({'stamp': stamp}, {'_id': 0}).to_list(None)
    master_names = {m['item_name'] for m in master_items}

    # Load ALL master item names (any stamp) — to detect when a mapped name
    # is itself a master item in another stamp (should NOT be counted here)
    all_master_items = await db.master_items.find({}, {'_id': 0, 'item_name': 1, 'stamp': 1}).to_list(None)
    all_master_names = {m['item_name'] for m in all_master_items}

    # Mappings: which transaction names resolve to items in this stamp
    mappings = await db.item_mappings.find({}, {'_id': 0}).to_list(None)
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
    opening = await db.opening_stock.find({}, {'_id': 0}).to_list(None)
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
    ).to_list(None)

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
    ).to_list(None)
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

