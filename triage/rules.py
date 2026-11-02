from triage.schemas import Decision,review

def decision(cls,ids,reason):
    return Decision(predicted_class=cls,recommendation='allow' if cls=='bona_fide' else 'escalate' if cls=='manual_review' else 'reject',evidence_ids=ids,contradictions=[],missing_data=[],rationale=reason)

def pad_only(evidence):
    v=next(x for x in evidence if x.group=='visual')
    if v.status!='ok':return {'predicted_class':'manual_review','recommendation':'escalate','evidence_ids':['v0'],'rationale':'PAD unavailable'}
    live=v.values['pad_label']=='live'
    return {'predicted_class':'live' if live else 'spoof','recommendation':'allow' if live else 'reject','evidence_ids':['v0'],'rationale':'Binary PAD argmax; no delivery attribution'}

def rules(evidence):
    by={e.evidence_id:e for e in evidence};v=by['v0'];c=by['c1']
    if c.status=='ok' and c.values.get('attestation')=='invalid' and c.values.get('capture_binding')=='mismatch':
        return decision('injection_attack',['c1'],'Attestation and binding both fail; synthetic scenario evidence')
    if v.status!='ok':return review(evidence,'Visual tool unavailable')
    if v.values['pad_label']=='spoof':
        if c.status=='ok' and c.values.get('capture_binding')=='mismatch':
            return review(evidence,'Spoof appearance and delivery anomaly conflict on attack attribution')
        return decision('presentation_attack',['v0'],'Spoof appearance without corroborated injection; heuristic attribution')
    if c.status!='ok' or c.values.get('capture_binding')!='match' or c.values.get('attestation')!='valid':
        return review(evidence,'Live score does not establish trustworthy delivery')
    return decision('bona_fide',['v0','c1'],'Live appearance and matching attested channel')

def merge(a,b,evidence):
    if a.predicted_class=='manual_review' or b.predicted_class=='manual_review':
        return review(evidence,'An analyst abstained')
    if a.predicted_class==b.predicted_class:cls=a.predicted_class
    elif a.predicted_class=='bona_fide':cls=b.predicted_class
    elif b.predicted_class=='bona_fide':cls=a.predicted_class
    else:return review(evidence,'Analysts disagree on attack type')
    d=decision(cls,sorted(set(a.evidence_ids+b.evidence_ids)),'Predefined conservative analyst merge')
    if a.predicted_class!=b.predicted_class:d.contradictions=['Analysts differ: '+a.predicted_class+' vs '+b.predicted_class]
    d.missing_data=sorted(set(a.missing_data+b.missing_data))
    return d
