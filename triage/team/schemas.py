"""Typed messages and agent reports. Every LLM output is validated against one of these models."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Verdict = Literal['bona_fide','presentation_attack','injection_attack','manual_review']
Risk = Literal['low','medium','high']
Recommendation = Literal['allow','reverify','block_escalate','escalate']
AgentName = Literal['orchestrator','liveness_analyst','channel_analyst','session_analyst','verifier','conclusion']
ANALYSTS = ('liveness_analyst','channel_analyst','session_analyst')

# Which recommendations are coherent with a verdict. Re-verification is offered only to a probably genuine
# user whose evidence is poor (e.g. PAD unavailable); an attacker is never given another automatic attempt.
ALLOWED = {'bona_fide':{'allow','reverify'},'presentation_attack':{'block_escalate'},'injection_attack':{'block_escalate'},'manual_review':{'escalate'}}
# Attack instruments per class (plan: attack reference). Presentation = artifact in front of a real camera;
# injection = media fed around the camera.
ATTACK_TYPES = {'bona_fide':{'none'},'presentation_attack':{'print','screen_replay','mask','unknown'},'injection_attack':{'virtual_camera','emulator','hooking','stream_substitution','unknown'},'manual_review':{'print','screen_replay','mask','virtual_camera','emulator','hooking','stream_substitution','unknown','none'}}

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

LivenessId = Literal['L1','L2','L3']
ChannelId = Literal['C1','C2']
SessionId = Literal['S1','S2','S3']

class EvidenceMap(Strict):
    """Evidence per analyst; the grammar only allows each agent's own tool IDs."""
    liveness_analyst: list[LivenessId] = []
    channel_analyst: list[ChannelId] = []
    session_analyst: list[SessionId] = []

class Message(Strict):
    """Plan section 7: typed JSON message between agents, stored in shared memory."""
    incident_id: str
    sender: AgentName
    recipient: AgentName
    type: Literal['task','result','recheck','verification','conclusion','status']
    status: Literal['done','error','unavailable','pending']
    payload: dict[str, Any]

class Task(Strict):
    agent: Literal['liveness_analyst','channel_analyst','session_analyst']
    focus: str = Field(max_length=300)

class OrchestratorPlan(Strict):
    tasks: list[Task] = Field(min_length=1, max_length=3)
    priority_signal: Literal['visual','channel','session','none']
    rationale: str = Field(min_length=1, max_length=600)

class OrchestratorStatus(Strict):
    final_status: Literal['completed','manual_review']
    limits_respected: bool
    journal_note: str = Field(min_length=1, max_length=600)

class LivenessReport(Strict):
    liveness_assessment: Literal['live','spoof','uncertain']
    models_agree: bool | None
    frame_quality: Literal['ok','low','unavailable']
    suspected_artifact: Literal['print','screen_replay','mask','none','unknown']
    risk: Risk
    confidence: int = Field(ge=0, le=100, description="percent")
    evidence_ids: list[LivenessId] = Field(min_length=1)
    findings: str = Field(min_length=1, max_length=800)

class ChannelReport(Strict):
    virtual_camera_signs: bool
    emulator_signs: bool
    hooking_signs: bool
    stream_anomalies: list[str]
    channel_risk: Risk
    confidence: int = Field(ge=0, le=100, description="percent")
    evidence_ids: list[ChannelId] = Field(min_length=1)
    findings: str = Field(min_length=1, max_length=800)

class SessionReport(Strict):
    attempts_last_hour: int | None
    linked_accounts: int | None
    ip_category: str | None
    session_risk: Risk
    confidence: int = Field(ge=0, le=100, description="percent")
    evidence_ids: list[SessionId] = Field(min_length=1)
    findings: str = Field(min_length=1, max_length=800)

REPORTS = {'liveness_analyst':LivenessReport,'channel_analyst':ChannelReport,'session_analyst':SessionReport}

class Verification(Strict):
    decision: Literal['accept','recheck','manual_review']
    recheck_agent: Literal['liveness_analyst','channel_analyst','session_analyst','none']
    recheck_question: str = Field(max_length=400)
    contradictions: list[str]
    missing_data: list[str]
    rationale: str = Field(min_length=1, max_length=800)

    @model_validator(mode='after')
    def target(self):
        if (self.decision=='recheck')!=(self.recheck_agent!='none'):raise ValueError('recheck requires exactly one target agent')
        return self

class FinalVerification(Verification):
    """After the single recheck cycle no further recheck can be expressed (lesson from protocol v1)."""
    decision: Literal['accept','manual_review']
    recheck_agent: Literal['none']

class Conclusion(Strict):
    verdict: Verdict
    attack_type: Literal['print','screen_replay','mask','virtual_camera','emulator','hooking','stream_substitution','unknown','none']
    risk_level: Risk
    confidence: int = Field(ge=0, le=100, description="percent")
    recommendation: Recommendation
    evidence: EvidenceMap
    contradictions: list[str]
    operator_report: str = Field(min_length=1, max_length=1500)

    @model_validator(mode='after')
    def coherent(self):
        if self.recommendation not in ALLOWED[self.verdict]:raise ValueError('recommendation inconsistent with verdict')
        if self.attack_type not in ATTACK_TYPES[self.verdict]:raise ValueError('attack type inconsistent with verdict')
        return self

    @classmethod
    def llm_schema(cls, verdicts=None):
        """Decoding grammar: one variant per verdict, so cross-field rules hold during generation, not only after."""
        base = cls.model_json_schema()
        defs = base.pop('$defs', None)
        variants = []
        for v in verdicts or ALLOWED:
            s = {**base, 'properties': dict(base['properties'])}
            s['properties']['verdict'] = {'const': v}
            s['properties']['attack_type'] = {'enum': sorted(ATTACK_TYPES[v])}
            s['properties']['recommendation'] = {'enum': sorted(ALLOWED[v])}
            s.pop('title', None);variants.append(s)
        out = {'anyOf': variants}
        if defs:out['$defs'] = defs
        return out

def fallback(reason, evidence=None):
    """Programmatic manual-review conclusion used on any technical failure. Never a guessed class."""
    return Conclusion(verdict='manual_review',attack_type='unknown',risk_level='high',confidence=0,recommendation='escalate',evidence=EvidenceMap(**(evidence or {})),contradictions=[],operator_report='Automatic triage not completed: '+reason)
