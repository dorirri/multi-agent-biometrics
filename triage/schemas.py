from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Class = Literal['bona_fide','presentation_attack','injection_attack','manual_review']
class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)

class Evidence(Strict):
    evidence_id: str
    group: Literal['visual','channel','history','check']
    provenance: Literal['model_on_real_media','synthetic','derived']
    observed_by: Literal['local_tool','client_claim','server_observation']
    status: Literal['ok','missing','error']
    values: dict[str,Any]

class AgentInput(Strict):
    incident_id: str
    evidence: list[Evidence]

    @model_validator(mode='after')
    def unique(self):
        ids=[x.evidence_id for x in self.evidence]
        if len(ids)!=len(set(ids)):raise ValueError('duplicate evidence IDs')
        return self

class Decision(Strict):
    predicted_class: Class
    recommendation: Literal['allow','reject','escalate']
    evidence_ids: list[str] = Field(min_length=1)
    contradictions: list[str]
    missing_data: list[str]
    rationale: str = Field(min_length=1,max_length=2000)
    request_check: Literal['none','consistency','visual_summary'] = 'none'

    @model_validator(mode='after')
    def action(self):
        expected={'bona_fide':'allow','presentation_attack':'reject','injection_attack':'reject','manual_review':'escalate'}
        if self.recommendation!=expected[self.predicted_class]:raise ValueError('inconsistent recommendation')
        return self

def validate_decision(raw, evidence):
    d=Decision.model_validate(raw)
    if not set(d.evidence_ids)<=set(x.evidence_id for x in evidence):
        raise ValueError('unknown evidence reference')
    return d

def review(evidence, reason):
    return Decision(predicted_class='manual_review',recommendation='escalate',evidence_ids=[x.evidence_id for x in evidence],contradictions=[],missing_data=[reason],rationale=reason)
