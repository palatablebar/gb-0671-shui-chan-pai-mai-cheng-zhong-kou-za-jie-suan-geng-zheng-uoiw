from app.modules.reconcile.rules import balance
from copy import deepcopy

def test_input_conservation_real(sample):
    assert sample['balance']['input']==53;assert sample['balance']['row_balanced']
def test_isolated_count_real(sample):
    assert sample['balance']['quarantined']==8
def test_money_real(sample):
    assert sample['balance']['amount']=='23708.91';assert sample['balance']['due']=='22540.41'
def test_missing_row_detected(sample):
    s=deepcopy(sample);s['records'].pop();assert balance(s)['row_balanced'] is False
def test_wrong_due_detected(sample):
    s=deepcopy(sample);s['final'][0]['due']='1';assert balance(s)['money_balanced'] is False
def test_clean_balance(clean):
    assert clean['balance']['quarantined']==0;assert clean['balance']['input']==42
def test_blocked_version(sample):
    s=deepcopy(sample);s['version_conflicts']=[{'ticket':'x'}];assert balance(s)['blocked']==1
