"""Denominators include abstentions, malformed outputs and tool failures."""
from collections import Counter
import csv
from triage.io import write_json

CLASSES=['bona_fide','presentation_attack','injection_attack']
def evaluate(predictions,labels):
    truth={r['incident_id']:r['scenario_class'] for r in labels}
    visual_truth={r['incident_id']:r.get('visual_source_label') for r in labels}
    out=[];matrices={}
    for method in sorted({r['method'] for r in predictions}):
        rows=[r for r in predictions if r['method']==method]
        if len({r['incident_id'] for r in rows})!=len(rows):raise ValueError('duplicate incident within method')
        n=len(rows);attacks=[r for r in rows if truth[r['incident_id']]!='bona_fide'];benign=[r for r in rows if truth[r['incident_id']]=='bona_fide']
        def metric(name,num,den):
            out.append({'method':method,'metric':name,'value':num/den if den else None,'numerator':num,'denominator':den,'n':n})
        metric('attack_allow_rate',sum(r['recommendation']=='allow' for r in attacks),len(attacks))
        metric('benign_reject_or_escalate_rate',sum(r['recommendation']!='allow' for r in benign),len(benign))
        metric('benign_reject_rate',sum(r['recommendation']=='reject' for r in benign),len(benign))
        metric('manual_review_rate',sum(r['predicted_class']=='manual_review' for r in rows),n)
        auto=[r for r in rows if r['predicted_class']!='manual_review'];metric('coverage',len(auto),n)
        for cls in CLASSES:
            subset=[r for r in rows if truth[r['incident_id']]==cls]
            metric('review_'+cls,sum(r['predicted_class']=='manual_review' for r in subset),len(subset))
        target=lambda r:visual_truth[r['incident_id']] if method=='A' else truth[r['incident_id']]
        actual=['live','spoof'] if method=='A' else CLASSES
        cols=actual+['manual_review']
        matrix=[[sum(target(r)==a and r['predicted_class']==p for r in rows) for p in cols] for a in actual]
        matrices[method]={'rows':actual,'columns':cols,'counts':matrix,'n':n}
        metric('selective_accuracy',sum(r['predicted_class']==target(r) for r in auto),len(auto))
        fs=[]
        for cls in actual:
            tp=sum(r['predicted_class']==cls and target(r)==cls for r in rows)
            fp=sum(r['predicted_class']==cls and target(r)!=cls for r in rows)
            fn=sum(r['predicted_class']!=cls and target(r)==cls for r in rows)
            metric('precision_'+cls,tp,tp+fp);metric('recall_'+cls,tp,tp+fn)
            metric('f1_'+cls,2*tp,2*tp+fp+fn)
            fs.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
        metric('macro_f1_binary' if method=='A' else 'macro_f1',sum(fs),len(fs))
        metric('triage_mean_seconds',sum(r['triage_seconds'] for r in rows),n)
        metric('feature_mean_seconds_per_incident_cached',sum(r['feature_seconds'] for r in rows),n)
        metric('calls_per_incident',sum(r['calls'] for r in rows),n)
        # Known tokens are lower bounds if an API fails before usage is returned.
        metric('known_input_tokens_per_incident',sum(r.get('input_tokens',0) for r in rows),n)
        metric('known_output_tokens_per_incident',sum(r.get('output_tokens',0) for r in rows),n)
        metric('error_rate',sum(r.get('errors',0)>0 for r in rows),n)
    return out,matrices

def save_metrics(path,predictions,labels):
    metrics,matrix=evaluate(predictions,labels)
    with (path/'metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['method','metric','value','numerator','denominator','n']);w.writeheader();w.writerows(metrics)
    write_json(path/'confusion_matrices.json',matrix)
    return metrics
