from collections import defaultdict
from decimal import Decimal
from app.reasons import reject

def pair(rows):
    groups=defaultdict(list)
    for row in rows: groups[(row['ticket'],row['version'])].append(row)
    pairs=[];bad=[]
    for (ticket,version),items in sorted(groups.items()):
        kinds={r['kind']:r for r in items}
        if len(items)!=2 or set(kinds)!={'gross','tare'}:
            bad.extend((r,'PAIR_MISSING','毛皮称重缺失或重复') for r in items);continue
        gross,tare=kinds['gross'],kinds['tare']
        if any(gross[k]!=tare[k] for k in ('fish','price','rate','replaces')):
            bad.extend((r,'PAIR_MISMATCH','毛皮品类或价格定义不一致') for r in items);continue
        net=Decimal(gross['weight_kg'])-Decimal(tare['weight_kg'])
        if net<0:
            bad.extend((r,'NEGATIVE_NET','毛重小于皮重') for r in items);continue
        pairs.append({'ticket':ticket,'version':version,'fish':gross['fish'],'gross_kg':gross['weight_kg'],
            'tare_kg':tare['weight_kg'],'net_kg':str(net),'price':gross['price'],'rate':gross['rate'],
            'replaces':gross['replaces'],'paid':gross['paid'],'lines':[gross['_line'],tare['_line']]})
    return pairs,bad

def apply(state):
    pairs,bad=pair(state['records'])
    bad_lines={r['_line'] for r,_,_ in bad}
    for row,code,detail in bad: reject(state,row,code,detail)
    state['records']=[r for r in state['records'] if r['_line'] not in bad_lines]
    state['pairs']=pairs
    state['views']['pairing']={'title':'毛皮配对','rows':pairs,'metrics':{'配对票':len(pairs),'问题行':len(bad)}}
