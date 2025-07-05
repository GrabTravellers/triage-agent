from typing import List

from pydantic import BaseModel


class LogEvent(BaseModel):
    timestamp: str
    message: str
    level: str
    service: str
    trace_id: str


class LogEventList(BaseModel):
    events: List[LogEvent]

    def __str__(self):
        return "\n".join(
            [
                f"{event.service}: {event.trace_id} - {event.timestamp} - {event.level} - {event.message}"
                for event in self.events
            ]
        )


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
