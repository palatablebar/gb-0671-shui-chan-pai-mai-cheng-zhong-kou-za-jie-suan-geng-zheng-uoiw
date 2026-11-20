from decimal import Decimal, ROUND_HALF_UP
from app.coerce import money

def settle(pair):
    billable=(Decimal(pair['net_kg'])*(1-Decimal(pair['rate']))).quantize(Decimal('.001'),rounding=ROUND_HALF_UP)
    return {**pair,'billable_kg':str(billable),'amount':money(billable*Decimal(pair['price']))}

def apply(state):
    state['settlements']=[settle(p) for p in state['pairs']]
    total=sum((Decimal(p['amount']) for p in state['settlements']),Decimal(0))
    state['views']['auction']={'title':'扣杂结算','rows':state['settlements'],'metrics':{'版本票':len(state['settlements']),'金额_CNY':money(total)}}
