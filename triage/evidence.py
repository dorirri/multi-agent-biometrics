from triage.schemas import AgentInput,Evidence

def build_input(incident,cache):
    visual=cache[incident['source_id']]
    fault=incident['tool_fault'] is not None
    e=[Evidence(evidence_id='v0',group='visual',provenance='model_on_real_media',observed_by='local_tool',status='error' if fault else visual['status'],values={'error':'controlled_tool_failure'} if fault else visual['values'])]
    c=incident['channel']
    # Distinguish client assertion from synthetic server-side observation.
    e.append(Evidence(evidence_id='c0',group='channel',provenance='synthetic',observed_by='client_claim',status='missing' if c is None else 'ok',values={} if c is None else {'virtual_camera':c['virtual_camera'],'note':incident['client_note']}))
    e.append(Evidence(evidence_id='c1',group='channel',provenance='synthetic',observed_by='server_observation',status='missing' if c is None else 'ok',values={} if c is None else {k:v for k,v in c.items() if k!='virtual_camera'}))
    e.append(Evidence(evidence_id='h0',group='history',provenance='synthetic',observed_by='server_observation',status='missing' if incident['history'] is None else 'ok',values={} if incident['history'] is None else {'previous_events':incident['history']}))
    return AgentInput(incident_id=incident['incident_id'],evidence=e)

def additional_check(evidence,kind):
    """Recompute known facts; no fresh source and no external/production call."""
    by={x.evidence_id:x for x in evidence}
    if kind=='visual_summary':
        values={'derived_from':['v0'],'already_observed':True,'visual_status':by['v0'].status,'summary':by['v0'].values}
    elif kind=='consistency':
        c=by['c1'];v=by['v0']
        values={'derived_from':['v0','c0','c1','h0'],'already_observed':True,'missing_or_failed':[x.evidence_id for x in evidence if x.status!='ok'],'live_with_binding_mismatch':v.values.get('pad_label')=='live' and c.values.get('capture_binding')=='mismatch'}
    else:raise ValueError('not an allowed tool')
    return Evidence(evidence_id='t0',group='check',provenance='derived',observed_by='local_tool',status='ok',values=values)
