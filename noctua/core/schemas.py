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
