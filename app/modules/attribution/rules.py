"""船户归户：证件尾号优先，船名可临时补证，同名多证一律不并票。"""
from collections import defaultdict
from decimal import Decimal
from app.coerce import money

CODES = {
    'DOCUMENT': '证件尾号归户',
    'BOAT_NAME_ALIAS': '船名唯一对应证件尾号，临时并入',
    'BOAT_NAME_CONFLICT': '同名船名对应多个证件尾号，暂不并票',
    'BOAT_UNVERIFIED': '只有船名，缺少证件尾号',
    'BOAT_MULTI': '同一票内船名不一致',
    'ID_CONFLICT': '同一票内证件尾号不一致',
    'NO_OWNER_EVIDENCE': '既无船名也无证件尾号',
    'BOAT_NAME_VARIANCE': '同一证件尾号登记了多个船名',
    'BOAT_NAME_SHARED': '同一船名登记了多个证件尾号，证件优先',
}


def _clean(value):
    return ' '.join((value or '').split())


def collect_evidence(state):
    """逐票收集船名/证件尾号证据，保持原始行号，不修改任何原始记录。"""
    by_line = {row['_line']: row for row in state.get('records', [])}
    by_ticket = defaultdict(list)
    for row in state.get('records', []):
        if 'boat' in row or 'id_tail' in row:
            by_ticket[(row['ticket'], row['version'])].append(row)
    evidence = []
    for ticket in state.get('final', []):
        rows = [by_line[n] for n in ticket['lines'] if n in by_line]
        if not rows:
            rows = by_ticket.get((ticket['ticket'], ticket['version']), [])
        line_rows = sorted(rows, key=lambda r: r['_line'])
        boats = sorted({_clean(r.get('boat')) for r in line_rows if _clean(r.get('boat'))})
        tails = sorted({_clean(r.get('id_tail')) for r in line_rows if _clean(r.get('id_tail'))})
        evidence.append({
            'ticket': ticket['ticket'],
            'version': ticket['version'],
            'boats': boats,
            'id_tails': tails,
            'lines': [r['_line'] for r in line_rows],
            'raw': [{
                'id': r.get('id', ''), 'line': r['_line'],
                'boat': _clean(r.get('boat')), 'id_tail': _clean(r.get('id_tail')),
                'weight_kg': r.get('weight_kg', ''), 'kind': r.get('kind', ''),
            } for r in line_rows],
            'amount': ticket['amount'],
            'paid': ticket['paid'],
            'due': ticket['due'],
        })
    return evidence


def resolve(evidence):
    """返回每个票的归属决定。证件尾号是权威证据；船名只在唯一指向时补证。"""
    boat_to_ids = defaultdict(set)
    id_to_boats = defaultdict(set)
    for item in evidence:
        if len(item['id_tails']) == 1:
            tail = item['id_tails'][0]
            for boat in item['boats']:
                boat_to_ids[boat].add(tail)
                id_to_boats[tail].add(boat)

    decisions = []
    for item in evidence:
        tails, boats = item['id_tails'], item['boats']
        ticket = item['ticket']
        if len(tails) > 1:
            decisions.append({**item, 'owner_key': None, 'owner_label': '未并票 ' + ticket,
                              'kind': 'unmerged', 'status': '待核实', 'code': 'ID_CONFLICT'})
            continue
        if len(tails) == 1:
            tail = tails[0]
            code = 'DOCUMENT'
            if len(boats) > 1:
                code = 'BOAT_NAME_VARIANCE'
            elif boats and len(boat_to_ids[boats[0]]) > 1:
                code = 'BOAT_NAME_SHARED'
            decisions.append({**item, 'owner_key': 'ID:' + tail, 'owner_label': '证件尾号 ' + tail,
                              'kind': 'document', 'status': '可付', 'code': code})
            continue
        # 无证件尾号，只能看船名
        if len(boats) > 1:
            decisions.append({**item, 'owner_key': None, 'owner_label': '未并票 ' + ticket,
                              'kind': 'unmerged', 'status': '待核实', 'code': 'BOAT_MULTI'})
            continue
        if not boats:
            decisions.append({**item, 'owner_key': None, 'owner_label': '未并票 ' + ticket,
                              'kind': 'unmerged', 'status': '待核实', 'code': 'NO_OWNER_EVIDENCE'})
            continue
        boat = boats[0]
        known = sorted(boat_to_ids.get(boat, set()))
        if len(known) == 1:
            decisions.append({**item, 'owner_key': 'ID:' + known[0], 'owner_label': '证件尾号 ' + known[0],
                              'kind': 'provisional', 'status': '可付', 'code': 'BOAT_NAME_ALIAS',
                              'alias_boat': boat})
        elif len(known) > 1:
            decisions.append({**item, 'owner_key': None, 'owner_label': '未并票 ' + ticket,
                              'kind': 'unmerged', 'status': '待核实', 'code': 'BOAT_NAME_CONFLICT',
                              'boats': boats, 'candidate_id_tails': known})
        else:
            decisions.append({**item, 'owner_key': None, 'owner_label': '未并票 ' + ticket,
                              'kind': 'unmerged', 'status': '待核实', 'code': 'BOAT_UNVERIFIED',
                              'alias_boat': boat})
    return decisions, boat_to_ids, id_to_boats


def _ticket_row(item):
    return {
        'ticket': item['ticket'], 'version': item['version'],
        'boat': '、'.join(item['boats']) or '—', 'id_tail': '、'.join(item['id_tails']) or '—',
        'lines': item['lines'], 'amount': item['amount'], 'paid': item['paid'], 'due': item['due'],
        'code': item['code'], 'detail': CODES[item['code']],
        'owner_key': item['owner_key'] or '—', 'owner_label': item['owner_label'],
        'kind': item['kind'], 'status': item['status'],
        'candidate_id_tails': '、'.join(item.get('candidate_id_tails', [])) if item.get('candidate_id_tails') else '',
    }


def settle(decisions):
    groups = defaultdict(list)
    unmerged = []
    for item in decisions:
        if item['owner_key']:
            groups[item['owner_key']].append(item)
        else:
            unmerged.append(item)

    owners = []
    for key in sorted(groups):
        items = sorted(groups[key], key=lambda r: r['ticket'])
        provisional = [r['ticket'] for r in items if r['kind'] == 'provisional']
        codes = sorted({r['code'] for r in items})
        amount = sum((Decimal(r['amount']) for r in items), Decimal(0))
        paid = sum((Decimal(r['paid']) for r in items), Decimal(0))
        due = sum((Decimal(r['due']) for r in items), Decimal(0))
        owners.append({
            'owner_key': key, 'owner_label': items[0]['owner_label'],
            'kind': 'provisional' if provisional else 'document',
            'status': '可付', 'codes': '、'.join(codes),
            'detail': '；'.join(dict.fromkeys(CODES[c] for c in codes)),
            'tickets': [r['ticket'] for r in items], 'ticket_count': len(items),
            'provisional_tickets': provisional,
            'amount': money(amount), 'paid': money(paid), 'due': money(due),
            'evidence_lines': [n for r in items for n in r['lines']],
        })

    held = []
    for item in sorted(unmerged, key=lambda r: r['ticket']):
        held.append({
            'owner_key': 'HOLD:' + item['ticket'], 'owner_label': item['owner_label'],
            'kind': 'unmerged', 'status': '待核实', 'codes': item['code'],
            'detail': CODES[item['code']], 'tickets': [item['ticket']], 'ticket_count': 1,
            'provisional_tickets': [],
            'amount': item['amount'], 'paid': item['paid'], 'due': item['due'],
            'evidence_lines': item['lines'],
        })
    return owners, held


def attribute(state):
    evidence = collect_evidence(state)
    decisions, boat_to_ids, id_to_boats = resolve(evidence)
    owners, held = settle(decisions)

    ticket_rows = [_ticket_row(item) for item in decisions]
    merged = [r for r in ticket_rows if r['status'] == '可付']
    unmerged = [r for r in ticket_rows if r['status'] != '可付']

    ticket_total = sum((Decimal(r['amount']) for r in decisions), Decimal(0))
    owner_total = sum((Decimal(o['amount']) for o in owners + held), Decimal(0))
    tickets_seen = [r['ticket'] for r in decisions]
    unique_assignment = len(tickets_seen) == len(set(tickets_seen)) and set(tickets_seen) == {f['ticket'] for f in state.get('final', [])}
    payable = sum((Decimal(o['amount']) for o in owners), Decimal(0))
    held_amount = sum((Decimal(o['amount']) for o in held), Decimal(0))
    conserved = ticket_total == owner_total == payable + held_amount and unique_assignment

    return {
        'owners': owners,
        'unmerged_owners': held,
        'merged': merged,
        'unmerged': unmerged,
        'evidence': [{
            'ticket': item['ticket'], 'version': item['version'],
            'boat': '、'.join(item['boats']) or '—', 'id_tail': '、'.join(item['id_tails']) or '—',
            'lines': '、'.join(str(n) for n in item['lines']),
            'raw_lines': '；'.join(f"{r['line']}:{r['kind']} {r['boat'] or '—'}/{r['id_tail'] or '—'}" for r in item['raw']),
            'owner_label': item['owner_label'], 'status': item['status'],
            'code': item['code'], 'detail': CODES[item['code']],
        } for item in decisions],
        'grouping': {
            'boat_to_ids': {k: sorted(v) for k, v in sorted(boat_to_ids.items())},
            'id_to_boats': {k: sorted(v) for k, v in sorted(id_to_boats.items())},
        },
        'totals': {
            'tickets': len(decisions), 'merged_tickets': len(merged), 'unmerged_tickets': len(unmerged),
            'owners': len(owners), 'unmerged_owners': len(held),
            'ticket_amount': money(ticket_total), 'owner_amount': money(owner_total),
            'payable': money(payable), 'held': money(held_amount),
        },
        'conservation': {
            'ticket_total': money(ticket_total), 'owner_total': money(owner_total),
            'payable': money(payable), 'held': money(held_amount),
            'difference': money(owner_total - ticket_total),
            'unique_assignment': unique_assignment, 'conserved': conserved,
        },
        'conserved': conserved,
    }


def apply(state):
    state['attribution'] = attribute(state)
    result = state['attribution']
    state['views']['attribution'] = {
        'title': '船户归户', 'rows': result['owners'],
        'merged': result['merged'], 'unmerged': result['unmerged'],
        'unmerged_owners': result['unmerged_owners'], 'evidence': result['evidence'],
        'grouping': result['grouping'],
        'metrics': {
            '可用户': result['totals']['owners'],
            '待核实票': result['totals']['unmerged_tickets'],
            '可付_CNY': result['totals']['payable'],
            '暂存_CNY': result['totals']['held'],
            '守恒': '是' if result['conserved'] else '否',
        },
    }
