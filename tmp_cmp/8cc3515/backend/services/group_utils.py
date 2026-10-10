"""Shared utilities for item-group-aware calculations.

All endpoints that need purchase cost, fine, or labour data should use
build_group_ledger() so that grouped items share a single weighted-average
cost basis derived from ALL member purchase entries.
"""


def build_group_maps(groups, mappings):
    """Build lookup structures for item groups and mappings.

    Returns:
        mapping_dict:      transaction_name  -> master_name
        member_to_leader:  member_name       -> group_leader_name
        group_members:     group_leader_name -> [member_names]
    """
    mapping_dict = {m['transaction_name']: m['master_name'] for m in mappings}
    member_to_leader = {}
    group_members = {}
    for g in groups:
        members = g.get('members', [])
        group_members[g['group_name']] = members
        for member in members:
            if member != g['group_name']:
                member_to_leader[member] = g['group_name']
    return mapping_dict, member_to_leader, group_members


def resolve_to_leader(name, mapping_dict, member_to_leader):
    """Resolve any item name (transaction or master) to its group leader."""
    master = mapping_dict.get(name, name)
    return member_to_leader.get(master, master)


def build_group_ledger(ledger_items, groups, mappings):
    """Combine purchase-ledger entries per item group.

    For each group the result is a single dict with weighted-average
    purchase_tunch and labour_per_kg computed from every member that
    has a ledger entry (including names that *map* to a member).

    Non-grouped items keep their own ledger entry unchanged.

    Returns:
        group_ledger: dict  name -> { purchase_tunch, labour_per_kg, ... }
    """
    ledger_map = {l['item_name']: l for l in ledger_items}
    mapping_dict = {m['transaction_name']: m['master_name'] for m in mappings}

    member_to_leader = {}
    group_members_map = {}
    for g in groups:
        group_members_map[g['group_name']] = g.get('members', [])
        for member in g.get('members', []):
            if member != g['group_name']:
                member_to_leader[member] = g['group_name']

    # Reverse mapping: master_name -> [transaction_names]
    reverse_mapping = {}
    for txn_name, master_name in mapping_dict.items():
        reverse_mapping.setdefault(master_name, []).append(txn_name)

    group_ledger = {}

    for group_name, members in group_members_map.items():
        total_wt = 0.0
        total_fine = 0.0
        total_labour = 0.0

        # Collect ledger entries for all group members AND transaction names
        # that map to those members
        all_names = set(members)
        for member in members:
            if member in reverse_mapping:
                all_names.update(reverse_mapping[member])

        for name in all_names:
            l = ledger_map.get(name)
            if l:
                wt = l.get('total_purchased_kg', 0)
                total_wt += wt
                total_fine += l.get('total_fine_kg', 0)
                total_labour += l.get('total_labour', 0)

        if total_wt > 0:
            entry = {
                'item_name': group_name,
                'purchase_tunch': total_fine / total_wt * 100,
                'labour_per_kg': total_labour / total_wt,
                'total_purchased_kg': total_wt,
                'total_fine_kg': total_fine,
                'total_labour': total_labour,
            }
            group_ledger[group_name] = entry
            # Also register under each member name for direct lookups
            for m in members:
                group_ledger[m] = entry

    # Non-grouped items keep their own ledger entry
    all_grouped = set()
    for members in group_members_map.values():
        all_grouped.update(members)

    for l in ledger_items:
        name = l['item_name']
        if name not in all_grouped and name not in group_ledger:
            group_ledger[name] = l

    return group_ledger
