from app.modules.auction.rules import settle
from decimal import Decimal

def test_original_real(sample):
    assert sample['settlements'][0]['amount']=='1168.50'
def test_correction_amount_real(sample):
    assert sample['settlements'][1]['amount']=='1285.35'
def test_price_real(sample):
    assert sample['settlements'][0]['billable_kg']=='95.000'
def test_zero_net(clean):
    assert settle(dict(clean['pairs'][0],net_kg='0'))['amount']=='0.00'
def test_no_deduction(clean):
    assert settle(dict(clean['pairs'][0],rate='0'))['amount']=='1230.00'
def test_half_cent_rounding(clean):
    # TRAP-10
    assert settle(dict(clean['pairs'][0],net_kg='1',rate='0',price='0.105'))['amount']=='0.11'
def test_large_decimal(clean):
    assert settle(dict(clean['pairs'][0],net_kg='9007199254740993',rate='0',price='1'))['amount']=='9007199254740993.00'
