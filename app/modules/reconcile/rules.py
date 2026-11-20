from decimal import Decimal
from app.coerce import money

def balance(state):
    c=state['counts'];accepted=len(state['records']);quarantined=len(state['quarantine'])
    explained=accepted+quarantined+c['blank']+c['duplicate']+c['repeated_header']
    total=sum((Decimal(r['amount']) for r in state['final']),Decimal(0))
    paid=sum((Decimal(r['paid']) for r in state['final']),Decimal(0));due=sum((Decimal(r['due']) for r in state['final']),Decimal(0))
    return {'input':c['input'],'accepted':accepted,'quarantined':quarantined,'blank':c['blank'],'duplicate':c['duplicate'],
      'repeated_header':c['repeated_header'],'row_balanced':explained==c['input'],'amount':money(total),'paid':money(paid),'due':money(due),
      'money_balanced':total==paid+due,'blocked':len(state['version_conflicts'])}

def apply(state):
    state['balance']=balance(state)
    state['views']['reconcile']={'title':'应付四账','rows':[state['balance']],'metrics':{'应付_CNY':state['balance']['amount'],'已付_CNY':state['balance']['paid'],'待付_CNY':state['balance']['due']}}
