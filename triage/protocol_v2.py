"""Exploratory state-aware action schemas. Original agents.py stays unchanged."""
import json
import time
import urllib.request
from typing import Literal
from triage.agents import LLM,SYSTEM,ROLES
from triage.schemas import Decision,Evidence,review
from triage.evidence import additional_check
from triage.rules import merge

class FinalDecision(Decision):
    request_check: Literal['none']='none'

FINAL_INSTRUCTION='This is a FINAL stage. No tool request is available. Return request_check="none". You may still choose manual_review if evidence is insufficient. Do not treat an unavailable action as evidence about the class.'
INITIAL_INSTRUCTION='This is a PRELIMINARY stage. At most one shared additional check can be executed by the orchestrator. A request is optional; request_check="none" is permitted. Requests are allocated by protocol, not by ground truth.'
ALLOCATION_RULE='D: context request has priority over visual request; select the first non-none in [context, visual]. Execute one tool and request only its requester to finalize. Preserve the other preliminary conclusion; record its unexecuted request without converting it to an error. Merge classes by original v1 rule.'

def validate(raw,evidence,final):
    d=(FinalDecision if final else Decision).model_validate(raw)
    if not set(d.evidence_ids)<=set(e.evidence_id for e in evidence):raise ValueError('unknown evidence reference')
    return d

class LocalLLMV2(LLM):
    def call(self,role,evidence,extra=None,max_tokens=600,*,final=False):
        schema=(FinalDecision if final else Decision).model_json_schema()
        state={'stage':'final' if final else 'preliminary','available_request_check':['none'] if final else ['none','consistency','visual_summary'],'instruction':FINAL_INSTRUCTION if final else INITIAL_INSTRUCTION}
        prompt={'role_task':ROLES[role],'schema':schema,'evidence':[e.model_dump() for e in evidence],'additional_data':extra or {},'protocol_state':state}
        body={'model':self.model,'temperature':0,'max_tokens':max_tokens,'seed':8217,'response_format':{'type':'json_object','schema':schema},'messages':[{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(prompt,ensure_ascii=False)}]}
        trace={'role':role,'model':self.model,'request':body,'status':'error','input_tokens':None,'output_tokens':None,'final_stage':final,'backend':'local','cost_usd':0}
        started=time.perf_counter()
        try:
            if self.calls>=self.max_calls:raise RuntimeError('run_call_limit')
            self.calls+=1;trace['request_sent']=True
            req=urllib.request.Request(self.base+'/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
            with self.opener.open(req,timeout=40) as response:response=json.load(response)
            usage=response.get('usage',{})
            trace.update(input_tokens=usage.get('prompt_tokens'),output_tokens=usage.get('completion_tokens'),response_model=response.get('model'),server_timings=response.get('timings'),finish_reason=response['choices'][0].get('finish_reason'))
            raw=response['choices'][0]['message']['content'];trace['raw_response']=raw
            decision=validate(json.loads(raw),evidence,final)
            trace['status']='ok';return decision,trace
        except Exception as exc:
            trace['error_type']=type(exc).__name__
            return review(evidence,'LLM failure: '+type(exc).__name__),trace
        finally:trace['seconds']=time.perf_counter()-started

class OrchestratorV2:
    def __init__(self,llm,check_tool=additional_check):self.llm=llm;self.check_tool=check_tool

    def run(self,method,inp):
        evidence=list(inp.evidence);calls=[];checks=[];events=[]
        def ask(role,ev,extra=None,final=False):
            if len(calls)>=4:
                events.append({'kind':'call_limit'})
                return review(ev,'Per-method call limit')
            d,t=self.llm.call(role,ev,extra,final=final);calls.append(t)
            return d
        def check(kind,owner):
            if checks:raise RuntimeError('Attempted second actual check')
            item={'kind':kind,'owner':owner,'status':'error'};checks.append(item)
            try:
                tool=self.check_tool(evidence,kind)
                if tool.status!='ok':raise RuntimeError('tool unavailable')
                item['status']='ok';evidence.append(tool);return tool
            except Exception as exc:
                item['error_type']=type(exc).__name__
                evidence.append(Evidence(evidence_id='t0',group='check',provenance='derived',observed_by='local_tool',status='error',values={'error':'additional_tool_unavailable','already_observed':True}))
                return None
        def failed():return any(t['status']!='ok' for t in calls)
        if method=='C':
            d=ask('single',evidence)
            if not failed() and d.request_check!='none':
                tool=check(d.request_check,'single')
                d=review(evidence,'Additional tool failed') if tool is None else ask('single',evidence,{'final_after_check':True,'check_is_reanalysis':True},final=True)
        elif method in ('D','E'):
            visual=[e for e in evidence if e.group=='visual'];context=[e for e in evidence if e.group in ('channel','history')]
            a=ask('visual',visual,final=method=='E');b=ask('context',context,final=method=='E')
            if method=='D':
                requests=[(role,obj,ev) for role,obj,ev in [('context',b,context),('visual',a,visual)] if obj.request_check!='none']
                if requests and not failed():
                    role,obj,ev=requests[0]
                    events.append({'kind':'allocation','selected_role':role,'requested_check':obj.request_check,'unexecuted_requests':[{'role':r,'check':x.request_check} for r,x,_ in requests[1:]],'rule':'context_before_visual'})
                    tool=check(obj.request_check,role)
                    if tool is None:d=review(evidence,'Additional tool failed')
                    else:
                        result=ask(role,list(ev)+[tool],{'final_after_check':True,'check_is_reanalysis':True},final=True)
                        if role=='visual':a=result
                        else:b=result
                        d=merge(a,b,evidence)
                else:d=merge(a,b,evidence)
            else:
                extra={'visual_analyst':a.model_dump(),'context_analyst':b.model_dump(),'analyst_errors':[c.get('error_type') for c in calls if c['status']!='ok'],'analysts_have_no_tool_actions':True}
                d=ask('verifier',evidence,extra)
                if not failed() and d.request_check!='none':
                    tool=check(d.request_check,'verifier')
                    d=review(evidence,'Additional tool failed') if tool is None else ask('verifier',evidence,{'previous_context':extra,'final_after_check':True,'check_is_reanalysis':True},final=True)
        else:raise ValueError('V2 supports only C/D/E')
        if failed() or any(e['kind']=='call_limit' for e in events):
            d=review(evidence,'Technical LLM failure; no automatic decision')
        d=validate(d.model_dump(),evidence,True)
        return d,{'calls':calls,'rechecks':len(checks),'checks':checks,'events':events,'new_independent_sources':0,'protocol_version':2}
