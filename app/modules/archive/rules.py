import hashlib, json

def archive_decision(state):
    ready=state['balance']['row_balanced'] and state['balance']['money_balanced'] and not state['balance']['blocked']
    if state.get('attribution') and not state['attribution']['conserved']:
        ready=False
    seal_source={'final':state['final']}
    if state.get('attribution'):
        seal_source['attribution']={'owners':state['attribution']['owners'],'unmerged':state['attribution']['unmerged'],
            'totals':state['attribution']['totals'],'conservation':state['attribution']['conservation']}
    seal=hashlib.sha256(json.dumps(seal_source,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    return {'seal':seal,'status':'可归档' if ready else '待处理','tickets':len(state['final']),'reasons':len(state['quarantine']),
            'owners':len(state['attribution']['owners']) if state.get('attribution') else 0,
            'unmerged':len(state['attribution']['unmerged']) if state.get('attribution') else 0,
            'attribution_conserved':bool(state.get('attribution',{}).get('conserved'))}

def apply(state):
    state['archive']=archive_decision(state)
    state['views']['archive']={'title':'结算封存','rows':state['version_audit'],'metrics':{'封存票':state['archive']['tickets'],'隔离证据':len(state['quarantine']),'状态':state['archive']['status']}}
