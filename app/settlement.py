"""船户归户结果的发布：同一证据幂等，失败保留旧版，原始凭证只增不删。"""
import base64, hashlib, json
from datetime import datetime, timezone
from app.errors import BusinessError
from app.store import connect


def voucher_digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _household_rows(result):
    attribution = result['attribution']
    rows = []
    for owner in attribution['owners']:
        rows.append(('可付', owner))
    for owner in attribution['unmerged_owners']:
        rows.append(('待核实', owner))
    return rows


def validate(result):
    attribution = result.get('attribution')
    if not attribution:
        raise BusinessError('INCOMPLETE_RUN', '批次尚未完成船户归户')
    conservation = attribution.get('conservation', {})
    if not attribution.get('conserved') or not conservation.get('conserved') or not conservation.get('unique_assignment'):
        raise BusinessError('ATTRIBUTION_NOT_CONSERVED', '归户金额或票号不守恒，禁止发布')
    totals = attribution['totals']
    if totals['owner_amount'] != totals['ticket_amount']:
        raise BusinessError('ATTRIBUTION_NOT_CONSERVED', '归户总额与成交票总额不一致，禁止发布')
    balance = result.get('balance')
    if balance and totals['ticket_amount'] != balance.get('amount'):
        raise BusinessError('ATTRIBUTION_NOT_CONSERVED', '归户总额与应付对账总额不一致，禁止发布')
    if len(attribution['owners']) + len(attribution['unmerged_owners']) == 0:
        raise BusinessError('ATTRIBUTION_EMPTY', '没有可发布的归户结果')
    return attribution


def publish(path, result, hook=None, expected_revision=None):
    """在一个事务内发布户级结果。hook 仅用于测试故障注入，提交前调用。"""
    attribution = validate(result)
    digest = result['manifest']['sha256']
    run_id = result['manifest']['run_id']
    revision = result.get('revision', 1)
    if expected_revision is not None and expected_revision != revision:
        raise BusinessError('STALE_VERSION', '复核版本已更新，请刷新', 409)
    con = connect(path)
    con.isolation_level = None
    try:
        con.execute('BEGIN IMMEDIATE')
        existing = con.execute('SELECT * FROM publications WHERE digest=?', (digest,)).fetchone()
        if existing and existing['status'] == '已发布':
            con.rollback()
            return {**json.loads(existing['payload']), 'reused': True}

        raw = base64.b64decode(result['input_snapshot']['bytes_b64'])
        con.execute('INSERT OR IGNORE INTO vouchers(id,bytes,created_at) VALUES(?,?,?)',
                    (voucher_digest(raw), raw, _now()))

        con.execute('DELETE FROM households WHERE digest=?', (digest,))
        for status, owner in _household_rows(result):
            con.execute('INSERT INTO households(digest,run_id,owner_key,status,payload) VALUES(?,?,?,?,?)',
                        (digest, run_id, owner['owner_key'], status, json.dumps(owner, ensure_ascii=False)))

        if hook is not None:
            hook(con)

        payload = {
            'digest': digest, 'run_id': run_id, 'revision': revision,
            'status': '已发布', 'published_at': _now(),
            'totals': attribution['totals'], 'conservation': attribution['conservation'],
            'households': len(attribution['owners']) + len(attribution['unmerged_owners']),
            'voucher': voucher_digest(raw),
        }
        con.execute('INSERT OR REPLACE INTO publications(digest,run_id,revision,status,payload,voucher,updated_at) VALUES(?,?,?,?,?,?,?)',
                    (digest, run_id, revision, '已发布', json.dumps(payload, ensure_ascii=False),
                     payload['voucher'], payload['published_at']))
        con.commit()
        return {**payload, 'reused': False}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def publication(path, digest):
    con = connect(path)
    try:
        row = con.execute('SELECT * FROM publications WHERE digest=?', (digest,)).fetchone()
        if not row:
            return None
        households = [dict(r) for r in con.execute(
            'SELECT owner_key,status,payload FROM households WHERE digest=? ORDER BY owner_key', (digest,))]
        stored = json.loads(row['payload'])
        stored['updated_at'] = row['updated_at']
        stored['revision'] = row['revision']
        stored['status'] = row['status']
        stored['households'] = [{
            'owner_key': h['owner_key'], 'status': h['status'], **json.loads(h['payload']),
        } for h in households]
        stored['count'] = len(households)
        return stored
    finally:
        con.close()


def vouchers(path):
    con = connect(path)
    try:
        return [dict(r) for r in con.execute('SELECT id,created_at,length(bytes) AS size FROM vouchers ORDER BY created_at')]
    finally:
        con.close()


def voucher_bytes(path, voucher_id):
    con = connect(path)
    try:
        row = con.execute('SELECT bytes FROM vouchers WHERE id=?', (voucher_id,)).fetchone()
        if not row:
            raise BusinessError('VOUCHER_NOT_FOUND', '原始凭证不存在', 404)
        return bytes(row['bytes'])
    finally:
        con.close()
