"""Six-agent team from the project plan: orchestrator + shared memory, three parallel analysts,
verifier with at most one addressed recheck, conclusion agent. Every step is a tool call or an LLM call
and is counted against the per-incident limits; any technical failure ends in manual review."""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Literal
from triage.team.schemas import (ANALYSTS,REPORTS,Conclusion,FinalVerification,OrchestratorPlan,OrchestratorStatus,Verification,fallback)
from triage.team.store import TaskQueue

TASKS={
 'orchestrator_plan':'You are the orchestrator. Do not analyse evidence. From the flag reason and the list of available data blocks, write a verification plan: one task per analyst (liveness_analyst, channel_analyst, session_analyst) with a short focus describing what that analyst should pay attention to, and name the signal group to prioritise.',
 'liveness_analyst':'You are the liveness analyst. Interpret ONLY the face evidence: L1 MiniFASNetV2 PAD, L2 the thesis PAD model (V_june, decision threshold chosen on LCC development data), L3 OpenCV face/quality. Say whether appearance looks live or spoof, whether the two models agree, frame quality, and the suspected presentation artifact. No tool measures the artifact type: use unknown for a suspected spoof unless a tool value directly supports a type, none for live. You cannot judge the delivery channel.',
 'channel_analyst':'You are the device and channel analyst. Look for injection-attack signs: C1 parsed device/stream metadata (client fields are untrusted), C2 signature lookup against known virtual cameras, emulators and hooking frameworks. Consider attestation, capture binding, timing gaps/jitter, resolution and fps. Dual-use camera apps and root alone are weak signals. Report the channel risk.',
 'session_analyst':'You are the session-context analyst. Use S1 attempt history of the account, S2 accounts linked to the same device or IP, S3 local IP range category. Look for retries, account enumeration from one device/IP and suspicious network categories. Shared mobile carrier NAT (CGNAT) legitimately links many accounts on one IP; one device used by many accounts is stronger. Report the session risk.',
 'verifier':'You are the verifier. Check that the three analyst reports are valid (V1) and faithful to the ORIGINAL tool evidence. V2.report_errors lists analyst claims that contradict tool facts; also look for unsupported certainty yourself. V2.cross_signal_conflicts are disagreements BETWEEN signal groups (for example a live-looking face with a virtual camera signature is the typical injection pattern): they are findings to pass to the conclusion agent, NOT errors and NOT by themselves a reason for recheck or manual review. List them in contradictions. Missing or failed tools (status error/missing/unavailable) cannot be fixed by a recheck: never recheck for them; note them in missing_data. Decide: accept (reports are faithful enough to conclude, even if signals conflict or some tools are unavailable), recheck (one analyst misread its own tool evidence; name it and ask a precise question), or manual_review (the reports are unusable).',
 'verifier_final':'You are the verifier after the single allowed recheck cycle. The rechecked analyst answered your question. No further recheck is possible. Cross-signal conflicts are findings for the conclusion, not errors. Decide accept (reports are now faithful enough to conclude) or manual_review (they are still unusable).',
 'conclusion':'You are the conclusion agent. Using the verified analyst reports, the verification result, the attack reference (K1) and similar resolved incidents (K2), classify the incident and write the operator conclusion. '
  'Definitions: presentation_attack = a physical artifact (print, screen replay, mask) is shown to the REAL camera; it is recognised from appearance (PAD spoof) while the channel looks normal. '
  'injection_attack = prepared media is fed AROUND the camera (virtual camera, emulator, hooking framework, substituted stream); the face often looks live and the evidence is in the channel: injection-tool signatures, failed attestation or capture binding, timing anomalies. '
  'A live-looking face together with channel injection signs is the typical injection pattern, not a presentation attack. attack_type must belong to the verdict: print/screen_replay/mask/unknown for presentation_attack; virtual_camera/emulator/hooking/stream_substitution/unknown for injection_attack; none for bona_fide. '
  'Recommendation: bona_fide -> allow, or reverify when the user is probably genuine but key evidence (e.g. PAD) is unavailable or of low quality; any attack -> block_escalate; manual_review -> escalate (use it when evidence is irreconcilable or too weak to decide). '
  'Give evidence per agent (agent -> evidence_ids), contradictions and a short operator report in plain language. Similar incidents are hints, not proof.',
 'orchestrator_status':'You are the orchestrator closing the incident. limits_check is computed by code and is authoritative. Choose completed when the conclusion passed verification and limits_check is ok; choose manual_review only if verification_decision is manual_review or limits_check is not ok. Write a one-sentence journal note. You cannot change the verdict.'}

class ManualConclusion(Conclusion):
    verdict: Literal['manual_review']
    recommendation: Literal['escalate']

    @classmethod
    def llm_schema(cls):return Conclusion.llm_schema(['manual_review'])

class LimitExceeded(Exception):pass

class Team:
    def __init__(self,llm,tools,store,max_steps=25,max_seconds=None,parallel=True):
        self.llm=llm;self.tools=tools;self.store=store;self.max_steps=max_steps;self.max_seconds=max_seconds;self.parallel=parallel

    def run(self,inc):
        iid=inc['incident_id'];steps=[];started=time.perf_counter();events=[]
        def step(kind,agent,name,fn,*a):
            if len(steps)>=self.max_steps:raise LimitExceeded('step_limit')
            if self.max_seconds and time.perf_counter()-started>self.max_seconds:raise LimitExceeded('time_limit')
            t=time.perf_counter()
            if kind=='llm':
                obj,trace=self.llm.call(agent,*a);trace['name']=name;steps.append(trace);return obj
            out=fn(*a);steps.append({'kind':'tool','agent':agent,'name':name,'status':out.get('status','ok') if isinstance(out,dict) else 'ok','seconds':time.perf_counter()-t});return out
        def done(conclusion,reason=None):
            if reason:events.append({'kind':'fallback','reason':reason})
            self.store.write_conclusion(iid,'T',conclusion.model_dump())
            llm_steps=[s for s in steps if s['kind']=='llm']
            return conclusion,{'steps':steps,'events':events,'wall_seconds':time.perf_counter()-started,'llm_calls':sum(s.get('request_sent',False) for s in llm_steps),'tool_calls':sum(s['kind']=='tool' for s in steps),'llm_errors':sum(s['status']!='ok' for s in llm_steps)}
        try:
            # 1. Orchestrator: register incident in shared memory, plan, enqueue tasks.
            available={'frames':inc['frames_count'],'device_metadata':inc['device'] is not None,'stream_metadata':bool(inc['stream']),'session_history':inc['history_available']}
            step('tool','orchestrator','state_store',lambda:self.store.post(incident_id=iid,sender='orchestrator',recipient='orchestrator',type='status',status='pending',payload={'event':'incident_received','available':available}).model_dump())
            plan=step('llm','orchestrator','plan',None,TASKS['orchestrator_plan'],{'incident_ref':iid,'flag_reason':inc['flag_reason'],'available_data':available},OrchestratorPlan)
            if plan is None:return done(fallback('orchestrator planning failed'),'llm_failure')
            queue=TaskQueue();focus={t.agent:t.focus for t in plan.tasks}
            missing=[a for a in ANALYSTS if a not in focus]
            if missing:events.append({'kind':'plan_completed_by_code','added':missing})
            def enqueue():
                for a in ANALYSTS:queue.push({'agent':a,'focus':focus.get(a,'mandatory baseline check')})
                return {'status':'ok','queued':len(queue.items)}
            step('tool','orchestrator','task_queue',enqueue)
            # 2. Analysts in parallel; each runs its tools, then one LLM interpretation.
            toolsets={'liveness_analyst':[('pad_minifasnet',self.tools.pad_minifasnet),('pad_thesis_vjune',self.tools.pad_thesis),('face_quality',self.tools.face_quality)],
                      'channel_analyst':[('parse_metadata',self.tools.parse_metadata),('signature_lookup',self.tools.signature_lookup)],
                      'session_analyst':[('history_query',self.tools.history_query),('linked_accounts',self.tools.linked_accounts),('ip_info_local',self.tools.ip_info)]}
            evidence={}
            def analyse(task,question=None,previous=None):
                agent=task['agent']
                if agent not in evidence:evidence[agent]=[step('tool',agent,name,fn,inc) for name,fn in toolsets[agent]]
                payload={'incident_ref':iid,'focus':task['focus'],'evidence':evidence[agent]}
                if question:payload.update(verifier_question=question,your_previous_report=previous)
                report=step('llm',agent,'recheck' if question else 'analyse',None,TASKS[agent],payload,REPORTS[agent])
                if report and not set(report.evidence_ids)<={e['evidence_id'] for e in evidence[agent]}:
                    events.append({'kind':'unknown_evidence_reference','agent':agent});report=None
                status='done' if report else 'error'
                self.store.post(incident_id=iid,sender=agent,recipient='orchestrator',type='result',status=status,payload=report.model_dump() if report else {})
                return agent,(report.model_dump() if report else None,status)
            tasks=queue.drain()
            if self.parallel:
                with ThreadPoolExecutor(len(tasks)) as pool:reports=dict(pool.map(analyse,tasks))
            else:reports=dict(analyse(t) for t in tasks)
            if any(status=='error' for _,status in reports.values()):return done(fallback('analyst output invalid',{a:[e['evidence_id'] for e in es] for a,es in evidence.items()}),'analyst_failure')
            # 3. Verifier: deterministic schema/consistency tools, then judgement; one recheck cycle.
            v1=step('tool','verifier','schema_validate',self.tools.schema_validate,reports,evidence)
            v2=step('tool','verifier','consistency_rules',self.tools.consistency_rules,reports,evidence)
            vin={'incident_ref':iid,'reports':{a:r for a,(r,_) in reports.items()},'tool_evidence':evidence,'V1':v1,'V2':v2}
            verification=step('llm','verifier','verify',None,TASKS['verifier'],vin,Verification)
            if verification is None:return done(fallback('verifier failed'),'llm_failure')
            self.store.post(incident_id=iid,sender='verifier',recipient='orchestrator',type='verification',status='done',payload=verification.model_dump())
            if verification.decision=='recheck':
                target=verification.recheck_agent;events.append({'kind':'recheck','agent':target,'question':verification.recheck_question})
                self.store.post(incident_id=iid,sender='orchestrator',recipient=target,type='recheck',status='pending',payload={'question':verification.recheck_question})
                agent,result=analyse({'agent':target,'focus':focus.get(target,'')},verification.recheck_question,reports[target][0])
                if result[1]=='error':return done(fallback('rechecked analyst failed'),'analyst_failure')
                reports[agent]=result
                v2=step('tool','verifier','consistency_rules',self.tools.consistency_rules,reports,evidence)
                vin.update(reports={a:r for a,(r,_) in reports.items()},V2=v2,first_verification=verification.model_dump())
                verification=step('llm','verifier','verify_final',None,TASKS['verifier_final'],vin,FinalVerification)
                if verification is None:return done(fallback('final verification failed'),'llm_failure')
                self.store.post(incident_id=iid,sender='verifier',recipient='orchestrator',type='verification',status='done',payload=verification.model_dump())
            # 4. Conclusion agent.
            k1=step('tool','conclusion','attack_reference',self.tools.attack_reference)
            k2=step('tool','conclusion','similar_incidents',self.tools.similar_incidents,inc)
            schema=ManualConclusion if verification.decision=='manual_review' else Conclusion
            cin={'incident_ref':iid,'verified_reports':{a:r for a,(r,_) in reports.items()},'verification':verification.model_dump(),'K1':k1,'K2':k2}
            conclusion=step('llm','conclusion','conclude',None,TASKS['conclusion'],cin,schema)
            if conclusion is None:return done(fallback('conclusion failed'),'llm_failure')
            known={e['evidence_id'] for es in evidence.values() for e in es}|{'V1','V2','K1','K2'}
            if not {x for ids in conclusion.evidence.model_dump().values() for x in ids}<=known:return done(fallback('conclusion cites unknown evidence'),'unknown_evidence_reference')
            conclusion=Conclusion.model_validate(conclusion.model_dump())
            step('tool','conclusion','write_conclusion',lambda:(self.store.post(incident_id=iid,sender='conclusion',recipient='orchestrator',type='conclusion',status='done',payload=conclusion.model_dump()),{'status':'ok'})[1])
            # 5. Orchestrator closes the incident; it may only downgrade to manual review.
            status=step('llm','orchestrator','close',None,TASKS['orchestrator_status'],{'incident_ref':iid,'verification_decision':verification.decision,'conclusion':{'verdict':conclusion.verdict,'recommendation':conclusion.recommendation,'confidence':conclusion.confidence},'limits_check':{'ok':len(steps)<self.max_steps and (not self.max_seconds or time.perf_counter()-started<=self.max_seconds),'steps_used':len(steps)+1,'max_steps':self.max_steps,'seconds_used':round(time.perf_counter()-started,1),'max_seconds':self.max_seconds}},OrchestratorStatus)
            if status is None:return done(fallback('orchestrator closing failed'),'llm_failure')
            self.store.post(incident_id=iid,sender='orchestrator',recipient='orchestrator',type='status',status='done',payload=status.model_dump())
            if status.final_status=='manual_review' and conclusion.verdict!='manual_review':
                events.append({'kind':'orchestrator_downgrade','original':conclusion.model_dump()})
                conclusion=fallback('orchestrator sent to manual review: '+status.journal_note,conclusion.evidence.model_dump())
            return done(conclusion)
        except LimitExceeded as e:
            return done(fallback(str(e)),str(e))
