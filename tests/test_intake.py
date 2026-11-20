from app.engine import evaluate
from app.errors import BusinessError
from app.config import ROOT
import pytest

def test_bom_real(sample):
    # TRAP-02
    assert sample['records'][0]['id']=='00001gross'
def test_legacy_encoding():
    # TRAP-01
    s=evaluate({'dataset':'legacy'});assert s['encoding']=='gb18030';assert s['records'][0]['fish']=='黄鱼'
def test_repeated_header_real(sample):
    # TRAP-04
    assert sample['counts']['repeated_header']==1
def test_bad_columns_real(sample):
    # TRAP-05
    assert next(r for r in sample['quarantine'] if r['code']=='COLUMN_COUNT')['line']==53
def test_duplicate_conflict_real(sample):
    # TRAP-14
    assert len([r for r in sample['quarantine'] if r['code']=='DUPLICATE_CONFLICT'])==2
def test_empty_states():
    # TRAP-18
    for text,code in [('', 'EMPTY_FILE'),('\n\n','BLANK_FILE'),((ROOT/'sample_data/clean.csv').read_text().splitlines()[0]+'\n','HEADER_ONLY')]:
        with pytest.raises(BusinessError) as e:evaluate({'csv_text':text})
        assert e.value.code==code
def test_leading_zero_real(clean):
    # TRAP-08
    assert clean['records'][0]['ticket']=='00001'
