from app.modules.correction.rules import select_versions

def test_current_real(sample):
    assert sample['final'][0]['version']==2
def test_only_delta_paid_real(sample):
    assert sample['final'][0]['due']=='116.85'
def test_not_double_paid_real(sample):
    assert sample['balance']['paid']=='1168.50'
def test_stale_branch(clean):
    # TRAP-26
    rows=[dict(r) for r in clean['settlements'][:2]];rows.append(dict(rows[-1],version=3,replaces='1'));final,bad,_=select_versions(rows);assert not final;assert bad[0]['code']=='STALE_CORRECTION'
def test_missing_base(clean):
    final,bad,_=select_versions(clean['settlements'][1:2]);assert not final;assert bad[0]['code']=='MISSING_BASE'
def test_reverse_versions(clean):
    a=select_versions(clean['settlements']);b=select_versions(list(reversed(clean['settlements'])));assert a==b
def test_overpayment_credit(clean):
    row=dict(clean['settlements'][0],paid='1200');final,_,_=select_versions([row]);assert final[0]['due']=='-31.50'
