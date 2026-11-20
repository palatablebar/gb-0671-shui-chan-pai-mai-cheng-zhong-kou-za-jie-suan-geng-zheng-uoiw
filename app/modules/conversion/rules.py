from app.coerce import number, money
from app.errors import BusinessError
from app.reasons import reject

def normalize(row):
    out=dict(row)
    factor={'kg':1,'t':1000,'公斤':1}.get(row['unit'])
    if factor is None: raise BusinessError('BAD_UNIT','称重单位不受支持')
    if row['kind'] not in {'gross','tare'}: raise BusinessError('BAD_KIND','称重类型无效')
    weight=number(row['weight'])*factor;price=number(row['price']);rate=number(row['rate'])
    paid=number(row['paid']);version=number(row['version'])
    if weight<0 or price<0 or paid<0 or not 0<=rate<1 or version<1 or version%1:
        raise BusinessError('INVALID_RANGE','重量、单价、扣杂率或版本越界')
    out.update(weight_kg=str(weight),price=str(price),rate=str(rate),paid=str(paid),version=int(version))
    if not row['ticket'].strip() or not row['fish'].strip(): raise BusinessError('UNKNOWN_REFERENCE','票号或品类缺失')
    return out

def apply(state):
    good=[]
    for row in state['records']:
        try: good.append(normalize(row))
        except BusinessError as error: reject(state,row,error.code,error.message)
    state['records']=good
    state['views']['conversion']={'title':'重量换算','rows':good,'metrics':{'规范行':len(good),'隔离行':len(state['quarantine'])}}
