from datetime import datetime
from ninja import Schema
from typing import Optional

class MissionCreate(Schema):
    goal: str
    producer_key: str
    repo_url: str = ""
    issue_url: str = ""
    inputs: dict = {}
    success_criteria: str = ""
    domain: str = "code"
    budget: dict = {}
    auto_act: bool = False

class MissionOut(Schema):
    id: int
    goal: str
    state: str
    state_reason: str
    producer_key: str
    repo_url: str
    issue_url: str
    budget: dict
    spent: dict
    needs_input_prompt: Optional[str] = None
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    signal_id: Optional[int] = None

class MissionListOut(Schema):
    id: int
    goal: str
    state: str
    state_reason: str
    producer_key: str
    spent: dict
    budget: dict
    created_at: str
    finished_at: Optional[str] = None

class PlanOut(Schema):
    id: int
    version: int
    steps: list[dict]
    rendered_md: str

class RespondIn(Schema):
    response: str

class ArtifactOut(Schema):
    id: int
    mission_id: int
    producer_key: str
    kind: str
    uri: str
    preview: dict
    validation: dict
    queue_state: str
    tool_id: Optional[int] = None
