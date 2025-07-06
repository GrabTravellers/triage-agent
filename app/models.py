from typing import List

from pydantic import BaseModel


class LogEvent(BaseModel):
    timestamp: str
    message: str
    level: str
    service: str
    trace_id: str

class TriageResponse(BaseModel):
    triage_summary: str
    triage_title: str


class APRSAssignee(BaseModel):
    type: str
    name: str


class APRSIncident(BaseModel):
    title: str
    affectedServices: List[str]
    affectedRequests: List[str]
    assignee: APRSAssignee
    createdBy: str
    status: str
    createdAt: str

class ResolutionPlanRequest(BaseModel):
    incident_id: str
    rca_title: str
    rca_summary: str
    logs: List[LogEvent]


class ResolutionPlanStep(BaseModel):
    step_number: int
    step_procedure: str
    step_aws_cli_command: str

class ResolutionPlanResponse(BaseModel):
    resolution_plan: List[ResolutionPlanStep]
    confidence_score: int