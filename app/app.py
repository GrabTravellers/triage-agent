import asyncio
import datetime
import json
from typing import Optional

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from litellm import acompletion
from loguru import logger

from app.models import (
    APRSAssignee,
    APRSIncident,
    LogEvent,
    TriageResponse,
)

# Load environment variables
load_dotenv()

# Constants
APRS_BASE_URL = "https://96ef-202-54-141-35.ngrok-free.app/api"
TRIAGE_AUTHOR = "triage_agent"
DEFAULT_ASSIGNEE = "John Doe"
RCA_DELAY_SECONDS = 10

# Create FastAPI instance
app = FastAPI(
    title="Triage Agent API",
    description="An intelligent triage agent for incident management and root cause analysis",
    version="1.0.0",
)


class APRSClient:
    """Client for interacting with APRS API."""

    def __init__(self, base_url: str = APRS_BASE_URL):
        self.base_url = base_url
        self.headers = {"Content-Type": "application/json"}

    async def _make_request(
        self, method: str, endpoint: str, data: dict = None
    ) -> Optional[dict]:
        """Make an HTTP request to the APRS API."""
        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.base_url}/{endpoint.lstrip('/')}"

                # Add debug logging
                logger.info(f"Making {method} request to: {url}")
                logger.info(f"Request payload: {data}")

                if method.upper() == "POST":
                    response = await client.post(url, json=data, headers=self.headers)
                else:
                    response = await client.request(method, url, headers=self.headers)

                response.raise_for_status()
                logger.info(
                    f"Successfully made {method} request to {endpoint}. Status: {response.status_code}"
                )

                # Handle empty responses
                if response.text.strip():
                    return response.json()
                else:
                    logger.info("Empty response received")
                    return {
                        "status": "success",
                        "message": "Request completed successfully",
                    }

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error occurred: {e.response.status_code} - {e.response.text}"
            )
            logger.error(f"Failed URL: {url}")
            logger.error(f"Request payload: {data}")
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"APRS API error: {e.response.text}",
            )
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            logger.error(f"Response content: {response.text}")
            raise HTTPException(
                status_code=500, detail="Invalid JSON response from APRS API"
            )
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to communicate with APRS API: {str(e)}"
            )

    async def create_incident(self, incident: APRSIncident) -> dict:
        """Create a new incident in APRS."""
        logger.info(f"Creating incident: {incident.title}")
        return await self._make_request("POST", "incidents", incident.model_dump())

    async def create_timeline_entry(
        self, incident_id: str, timeline_type: str, payload: dict
    ) -> dict:
        """Create a timeline entry for an incident."""
        endpoint = f"incidents/{incident_id}/timeline/{timeline_type}/audit-trail"
        logger.info(
            f"Creating timeline entry for incident {incident_id}: {timeline_type}"
        )
        return await self._make_request("POST", endpoint, payload)

    async def create_root_cause_analysis(self, incident_id: str, analysis: str) -> dict:
        """Create a root cause analysis for an incident."""
        endpoint = f"incidents/{incident_id}/root-cause"
        payload = {"analysis": analysis}
        logger.info(f"Creating root cause analysis for incident {incident_id}")
        return await self._make_request("POST", endpoint, payload)


async def create_incident_timeline_entries(
    aprs_client: APRSClient,
    incident_id: str,
    log_events: list[LogEvent],
    triage_title: str,
) -> None:
    """Create all timeline entries for an incident."""
    current_time = str(datetime.datetime.now())

    # Convert LogEvent objects to serializable format
    log_snippet = "\n".join(
        [
            f"{event.service}: {event.trace_id} - {event.timestamp} - {event.level} - {event.message}"
            for event in log_events
        ]
    )

    # Create incident-detected timeline entry
    incident_detected_payload = {
        "status": "completed",
        "logSnippet": log_snippet,
        "timestamp": current_time,
        "author": TRIAGE_AUTHOR,
    }

    try:
        await aprs_client.create_timeline_entry(
            incident_id, "incident-detected", incident_detected_payload
        )
    except Exception as e:
        logger.error(f"Failed to create incident-detected timeline entry: {e}")

    # Create root-cause-analysis timeline entry (in_progress)
    rca_request_payload = {
        "status": "in_progress",
        "logSnippet": f"RCA requested for {triage_title}",
        "timestamp": current_time,
        "author": TRIAGE_AUTHOR,
    }

    try:
        await aprs_client.create_timeline_entry(
            incident_id, "root-cause-analysis", rca_request_payload
        )
    except Exception as e:
        logger.error(
            f"Failed to create root-cause-analysis request timeline entry: {e}"
        )


async def complete_rca_process(
    aprs_client: APRSClient, incident_id: str, triage_title: str, triage_summary: str
) -> None:
    """Complete the RCA process with a delay."""
    try:
        # Use asyncio.sleep instead of time.sleep to avoid blocking
        await asyncio.sleep(RCA_DELAY_SECONDS)

        # Create root-cause-analysis completion timeline entry
        rca_completion_payload = {
            "status": "completed",
            "logSnippet": f"RCA performed for {triage_title}",
            "timestamp": str(datetime.datetime.now()),
            "author": TRIAGE_AUTHOR,
        }

        await aprs_client.create_timeline_entry(
            incident_id, "root-cause-analysis", rca_completion_payload
        )

        # Create the actual root cause analysis
        await aprs_client.create_root_cause_analysis(incident_id, triage_summary)

        # Create resolution-plan timeline entry (pending)
        resolution_payload = {
            "status": "pending",
            "logSnippet": f"RCA performed for {triage_title}",
            "timestamp": str(datetime.datetime.now()),
            "author": TRIAGE_AUTHOR,
        }

        await aprs_client.create_timeline_entry(
            incident_id, "resolution-plan", resolution_payload
        )

    except Exception as e:
        logger.error(f"Failed to complete RCA process: {e}")


async def analyze_logs_with_ai(log_events: list[LogEvent]) -> TriageResponse:
    """Analyze log events using AI to determine root cause."""
    try:
        response = await acompletion(
            model="anthropic.claude-3-5-haiku-20241022-v1:0",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a triage agent and an expert at root cause analysis. "
                        "You will be given a list of logs, and you need to provide a short summary "
                        "of the root cause of the issue."
                    ),
                },
                {
                    "role": "user",
                    "content": f"The log events are as follows:\n\n{log_events}",
                },
            ],
            response_format=TriageResponse,
        )

        return TriageResponse.model_validate(
            json.loads(response.choices[0].message.content)
        )

    except Exception as e:
        logger.error(f"Failed to analyze logs with AI: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze logs with AI")


@app.post("/api/v1/triage", response_model=TriageResponse)
async def triage_logs(log_events: list[LogEvent]):
    """
    Triage logs to identify issues and create incidents.

    This endpoint:
    1. Analyzes logs using AI to determine root cause
    2. Creates an incident in APRS
    3. Creates timeline entries for the incident
    4. Initiates and completes RCA process
    """
    if not log_events:
        raise HTTPException(status_code=400, detail="No log events provided")

    # Analyze logs with AI
    triage_response = await analyze_logs_with_ai(log_events)

    # Create APRS client
    aprs_client = APRSClient()

    # Create incident
    incident_data = APRSIncident(
        title=triage_response.triage_title,
        affectedServices=list(set(log_event.service for log_event in log_events)),
        affectedRequests=list(set(log_event.trace_id for log_event in log_events)),
        assignee=APRSAssignee(type="aprs", name=DEFAULT_ASSIGNEE),
        createdBy=TRIAGE_AUTHOR,
        status="In Progress",
        createdAt=str(datetime.datetime.now()),
    )

    incident = await aprs_client.create_incident(incident_data)
    incident_id = incident["incidentId"]

    # Create timeline entries
    await create_incident_timeline_entries(
        aprs_client, incident_id, log_events, triage_response.triage_title
    )

    # Complete RCA process asynchronously
    asyncio.create_task(
        complete_rca_process(
            aprs_client,
            incident_id,
            triage_response.triage_title,
            triage_response.triage_summary,
        )
    )

    logger.info(
        f"Successfully triaged incident {incident_id}: {triage_response.triage_title}"
    )
    return triage_response


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": str(datetime.datetime.now())}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
