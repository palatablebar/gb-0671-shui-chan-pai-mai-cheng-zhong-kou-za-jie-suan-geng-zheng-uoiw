import hashlib, json

def archive_decision(state):
    ready=state['balance']['row_balanced'] and state['balance']['money_balanced'] and not state['balance']['blocked']
    seal=hashlib.sha256(json.dumps(state['final'],ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {'seal':seal,'status':'可归档' if ready else '待处理','tickets':len(state['final']),'reasons':len(state['quarantine'])}

def apply(state):
    state['archive']=archive_decision(state)
    state['views']['archive']={'title':'结算封存','rows':state['version_audit'],'metrics':{'封存票':state['archive']['tickets'],'隔离证据':len(state['quarantine']),'状态':state['archive']['status']}}
