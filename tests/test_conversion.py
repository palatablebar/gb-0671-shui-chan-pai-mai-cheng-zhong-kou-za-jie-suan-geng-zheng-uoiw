from app.modules.conversion.rules import normalize
from app.errors import BusinessError
import pytest

def test_normalized_real(sample):
    assert sample['records'][0]['weight_kg']=='115'
def test_sentinel_real(sample):
    # TRAP-07
    assert next(r for r in sample['quarantine'] if r['id']=='bad-1')['code']=='MISSING_VALUE'
def test_unit_bad_real(sample):
    assert next(r for r in sample['quarantine'] if r['id']=='bad-2')['code']=='BAD_UNIT'
def test_tonnes_counterexample(clean):
    # TRAP-15
    row=dict(clean['records'][0],weight='0.115',unit='t');assert normalize(row)['weight_kg']=='115.000'
def test_fullwidth_thousands(clean):
    # TRAP-06
    row=dict(clean['records'][0],weight='１,２３４.５');assert normalize(row)['weight_kg']=='1234.5'
def test_nan_refused(clean):
    with pytest.raises(BusinessError):normalize(dict(clean['records'][0],weight='NaN'))
def test_negative_weight(clean):
    with pytest.raises(BusinessError):normalize(dict(clean['records'][0],weight='-1'))
