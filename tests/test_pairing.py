from app.modules.pairing.rules import pair

def test_pair_real(sample):
    assert len(sample['pairs'])==21
def test_pair_net_real(sample):
    assert sample['pairs'][0]['net_kg']=='100'
def test_orphan_real(sample):
    assert next(r for r in sample['quarantine'] if r['id']=='bad-3')['code']=='PAIR_MISSING'
def test_negative_real(sample):
    assert next(r for r in sample['quarantine'] if r['id']=='bad-4')['code']=='NEGATIVE_NET'
def test_pair_definition_mismatch(clean):
    rows=[dict(r) for r in clean['records'][:2]];rows[1]['price']='9';pairs,bad=pair(rows);assert pairs==[];assert bad[0][1]=='PAIR_MISMATCH'
def test_duplicate_kind(clean):
    rows=[dict(r) for r in clean['records'][:2]];rows[1]['kind']='gross';pairs,bad=pair(rows);assert not pairs;assert len(bad)==2
def test_pair_input_order(clean):
    forward,_=pair(clean['records']);reverse,_=pair(list(reversed(clean['records'])));assert forward==reverse
