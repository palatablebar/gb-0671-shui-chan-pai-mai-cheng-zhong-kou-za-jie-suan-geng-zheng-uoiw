import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main, settlement, store
from app.engine import evaluate
from app.errors import BusinessError


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', str(tmp_path / 'test.sqlite'))
    return TestClient(main.app)


# ---------- resolution rules ----------

def test_document_tail_wins_over_boat(sample):
    grouped = {o['owner_key']: o for o in sample['attribution']['owners']}
    # 00013 船名与 1208 相同，但证件尾号 9999 独立成户，不并到 8891。
    assert '00013' in grouped['ID:9999']['tickets']
    assert '00013' not in grouped['ID:8891']['tickets']


def test_boat_name_aliases_unique_document(sample):
    grouped = {o['owner_key']: o for o in sample['attribution']['owners']}
    # 00010 只有船名 5002；该船名只对应证件尾号 6677，临时并入。
    assert '00010' in grouped['ID:6677']['tickets']
    assert '00010' in grouped['ID:6677']['provisional_tickets']
    assert grouped['ID:6677']['kind'] == 'provisional'
    # 00005 没有船名但证件尾号 8891 完整，走证件而非临时补证。
    assert '00005' in grouped['ID:8891']['tickets']
    assert '00005' not in grouped['ID:8891']['provisional_tickets']


def test_same_boat_multi_documents_not_merged(sample):
    unmerged = {r['ticket']: r for r in sample['attribution']['unmerged']}
    assert unmerged['00004']['code'] == 'BOAT_NAME_CONFLICT'
    assert unmerged['00004']['candidate_id_tails'] == '8891、9999'
    # 00008 船名 3001 对应 4412 与 5534，两侧都已有证件，不能并。
    assert unmerged['00008']['code'] == 'BOAT_NAME_CONFLICT'


def test_boat_without_document_held(sample):
    unmerged = {r['ticket']: r for r in sample['attribution']['unmerged']}
    assert unmerged['00011']['code'] == 'BOAT_UNVERIFIED'
    assert unmerged['00012']['code'] == 'BOAT_UNVERIFIED'


def test_no_evidence_held(sample):
    unmerged = {r['ticket']: r for r in sample['attribution']['unmerged']}
    assert unmerged['00020']['code'] == 'NO_OWNER_EVIDENCE'


def test_conflicting_documents_in_same_ticket_hold():
    from app.config import ROOT
    text = (ROOT / 'sample_data/clean.csv').read_text()
    lines = text.splitlines()
    gross = next(i for i, line in enumerate(lines) if line.startswith('00001v2gross,'))
    lines[gross] = lines[gross].replace(',浙渔1101,1101', ',浙渔1101,9991')
    # 00001 毛重行尾号 9991、皮重行尾号 1101，整票不并，且总额守恒。
    state = evaluate({'csv_text': '\n'.join(lines)})
    result = state['attribution']
    item = next(r for r in result['evidence'] if r['ticket'] == '00001')
    assert item['code'] == 'ID_CONFLICT'
    assert '00001' in {r['ticket'] for r in result['unmerged']}
    assert result['conserved']


def test_all_documented_clean_batch_merges_by_tail(clean):
    result = clean['attribution']
    assert result['totals']['unmerged_tickets'] == 0
    grouped = {o['owner_key']: o for o in result['owners']}
    # 船名 浙渔1208 对应 8891 与 9999 两个尾号，证件优先，00013 独立。
    assert grouped['ID:8891']['tickets'] == ['00002', '00003', '00004', '00005']
    assert grouped['ID:1301']['tickets'] == ['00013']
    assert grouped['ID:4412']['tickets'] == ['00006', '00007', '00008']


def test_legacy_batch_merges_same_as_clean():
    legacy = evaluate({'dataset': 'legacy'})
    assert legacy['attribution']['totals'] == evaluate({'dataset': 'clean'})['attribution']['totals']


# ---------- conservation ----------

def test_attribution_amount_conserved(sample):
    result = sample['attribution']
    assert result['conserved']
    assert result['conservation']['ticket_total'] == '23708.91'
    assert result['conservation']['owner_total'] == '23708.91'
    assert result['conservation']['payable'] == '15307.39'
    assert result['conservation']['held'] == '8401.52'
    assert result['conservation']['difference'] == '0.00'


def test_every_ticket_assigned_exactly_once(sample):
    tickets = [t for o in sample['attribution']['owners'] + sample['attribution']['unmerged_owners'] for t in o['tickets']]
    assert sorted(tickets) == sorted(f['ticket'] for f in sample['final'])
    assert len(tickets) == len(set(tickets))


def test_unmerged_amounts_add_up(sample):
    result = sample['attribution']
    owners = sum((__import__('decimal').Decimal(o['amount']) for o in result['owners']), __import__('decimal').Decimal(0))
    held = sum((__import__('decimal').Decimal(o['amount']) for o in result['unmerged_owners']), __import__('decimal').Decimal(0))
    assert str(owners) == result['totals']['payable']
    assert str(held) == result['totals']['held']


def test_raw_evidence_lines_preserved(sample):
    evidence = {r['ticket']: r for r in sample['attribution']['evidence']}
    assert evidence['00001']['lines'] == '42、43'
    assert evidence['00001']['raw_lines'].startswith('42:gross 浙渔1101/1101')


def test_attribution_does_not_mutate_records(sample):
    before = [(r['_line'], r.get('boat'), r.get('id_tail')) for r in sample['records']]
    again = evaluate()
    after = [(r['_line'], r.get('boat'), r.get('id_tail')) for r in again['records']]
    assert before == after


# ---------- publication: idempotency, failure rollback, vouchers ----------

def test_publish_idempotent_same_digest(tmp_path, sample):
    path = str(tmp_path / 'db.sqlite')
    first = settlement.publish(path, sample)
    rows_first = settlement.publication(path, sample['manifest']['sha256'])
    second = settlement.publish(path, sample)
    rows_second = settlement.publication(path, sample['manifest']['sha256'])
    assert first['reused'] is False and second['reused'] is True
    assert rows_first['count'] == rows_second['count']
    assert [h['owner_key'] for h in rows_first['households']] == [h['owner_key'] for h in rows_second['households']]


def test_rerun_same_evidence_does_not_add_households(tmp_path):
    path = str(tmp_path / 'db.sqlite')
    first = evaluate()
    rerun = evaluate(snapshot=first['input_snapshot'])
    assert first['manifest']['sha256'] == rerun['manifest']['sha256']
    settlement.publish(path, first)
    settlement.publish(path, rerun)
    con = sqlite3.connect(path)
    assert con.execute('SELECT COUNT(*) FROM households').fetchone()[0] == first['attribution']['totals']['owners'] + first['attribution']['totals']['unmerged_owners']
    assert con.execute('SELECT COUNT(*) FROM vouchers').fetchone()[0] == 1
    con.close()


def test_failed_publish_keeps_previous_attribution(tmp_path):
    path = str(tmp_path / 'db.sqlite')
    good = evaluate()
    settlement.publish(path, good)
    previous = settlement.publication(path, good['manifest']['sha256'])

    def boom(con):
        raise RuntimeError('publish interrupted')

    changed = evaluate({'overrides': {'market': 'test'}}) if False else evaluate({'dataset': 'clean'})
    with pytest.raises(RuntimeError):
        settlement.publish(path, changed, hook=boom)
    # 新摘要无任何半成品记录
    assert settlement.publication(path, changed['manifest']['sha256']) is None
    # 旧版仍在且行级不变
    still = settlement.publication(path, good['manifest']['sha256'])
    assert still['count'] == previous['count']
    assert [h['owner_key'] for h in still['households']] == [h['owner_key'] for h in previous['households']]
    con = sqlite3.connect(path)
    assert con.execute('SELECT COUNT(*) FROM vouchers').fetchone()[0] == 1
    con.close()


def test_same_evidence_republish_skips_write(tmp_path):
    path = str(tmp_path / 'db.sqlite')
    good = evaluate()
    settlement.publish(path, good)
    previous = settlement.publication(path, good['manifest']['sha256'])

    def boom(con):
        raise RuntimeError('hook must not run on reuse')

    reused = settlement.publish(path, good, hook=boom)
    assert reused['reused'] is True
    still = settlement.publication(path, good['manifest']['sha256'])
    assert [h['owner_key'] for h in still['households']] == [h['owner_key'] for h in previous['households']]
    assert still['updated_at'] == previous['updated_at']


def test_publish_rejects_non_conserved(tmp_path, sample):
    path = str(tmp_path / 'db.sqlite')
    broken = {**sample, 'attribution': {**sample['attribution'], 'conserved': False}}
    with pytest.raises(BusinessError) as error:
        settlement.publish(path, broken)
    assert error.value.code == 'ATTRIBUTION_NOT_CONSERVED'
    assert settlement.publication(path, sample['manifest']['sha256']) is None


def test_voucher_bytes_untouched_and_retrievable(tmp_path, sample):
    path = str(tmp_path / 'db.sqlite')
    settlement.publish(path, sample)
    rows = settlement.vouchers(path)
    assert len(rows) == 1
    raw = settlement.voucher_bytes(path, rows[0]['id'])
    assert raw == __import__('base64').b64decode(sample['input_snapshot']['bytes_b64'])


def test_http_publish_and_idempotency(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    rid = run['manifest']['run_id']
    first = c.post(f'/api/runs/{rid}/publish', json={})
    second = c.post(f'/api/runs/{rid}/publish', json={})
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()['reused'] is False and second.json()['reused'] is True
    assert c.get(f'/api/runs/{rid}/publication').json()['status'] == '已发布'


def test_http_publication_before_publish(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    assert c.get(f"/api/runs/{run['manifest']['run_id']}/publication").json()['status'] == '未发布'


def test_http_voucher_download(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    c.post(f"/api/runs/{run['manifest']['run_id']}/publish", json={})
    listing = c.get('/api/vouchers').json()
    assert len(listing) == 1
    response = c.get('/api/vouchers/' + listing[0]['id'])
    assert response.status_code == 200
    assert response.content == __import__('base64').b64decode(run['input_snapshot']['bytes_b64'])


def test_attribution_page_renders(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    rid = run['manifest']['run_id']
    html = c.get('/attribution?run_id=' + rid).text
    for token in ('船户归户', '未并票', '证据对照', '同名冲突图谱', '守恒校验'):
        assert token in html
    for ticket in ('00004', '00008', '00011', '00020'):
        assert ticket in html


def test_archive_sees_publication_flag(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    rid = run['manifest']['run_id']
    assert c.post(f'/api/runs/{rid}/publish', json={}).status_code == 200
    html = c.get('/archive?run_id=' + rid).text
    assert '已发布' in html


def test_publish_stale_revision_rejected(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    rid = run['manifest']['run_id']
    assert c.post(f'/api/runs/{rid}/publish', json={'revision': 99}).status_code == 409
    assert c.get(f'/api/runs/{rid}/publication').json()['status'] == '未发布'
    assert c.post(f'/api/runs/{rid}/publish', json={'revision': 1}).status_code == 200


def test_publish_survives_store_reopen(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    run = c.post('/api/runs', json={}).json()
    rid = run['manifest']['run_id']
    c.post(f'/api/runs/{rid}/publish', json={})
    fresh = TestClient(main.app)
    body = fresh.get(f'/api/runs/{rid}/publication').json()
    assert body['status'] == '已发布'
    assert body['count'] == run['attribution']['totals']['owners'] + run['attribution']['totals']['unmerged_owners']


def test_boat_variance_same_document_still_merges():
    from app.config import ROOT
    text = (ROOT / 'sample_data/clean.csv').read_text()
    lines = text.splitlines()
    gross = next(i for i, line in enumerate(lines) if line.startswith('00001v2gross,'))
    lines[gross] = lines[gross].replace(',浙渔1101,1101', ',浙渔9999,1101')
    result = evaluate({'csv_text': '\n'.join(lines)})['attribution']
    item = next(r for r in result['evidence'] if r['ticket'] == '00001')
    # 同票船名不一致但证件尾号一致：按证件归户，原因码记录船名差异。
    assert item['code'] == 'BOAT_NAME_VARIANCE'
    assert item['status'] == '可付'
    assert result['conserved']


def test_header_without_optional_columns_still_accepted():
    from app.config import ROOT
    text = (ROOT / 'sample_data/clean.csv').read_text()
    lines = text.splitlines()
    stripped = ['\n'.join(','.join(line.split(',')[:11]) for line in lines)]
    result = evaluate({'csv_text': stripped[0]})
    assert result['attribution']['totals']['tickets'] == 20
    assert result['attribution']['totals']['merged_tickets'] == 0
    assert result['attribution']['conserved']


def test_unknown_extra_column_rejected():
    from app.config import ROOT
    from app.errors import BusinessError
    text = (ROOT / 'sample_data/clean.csv').read_text().replace(',boat,id_tail', ',boat,id_tail,mystery')
    with pytest.raises(BusinessError) as error:
        evaluate({'csv_text': text})
    assert error.value.code == 'BAD_HEADER'
