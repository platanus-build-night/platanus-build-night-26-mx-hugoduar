from django.db import models

MISSION_STATES = [(s, s) for s in ["queued", "running", "succeeded", "failed", "stopped", "needs_input"]]
SIGNAL_SOURCES = [(s, s) for s in ["sentry", "manual"]]
ROUTING_STATUSES = [(s, s) for s in ["pending", "routed", "ignored", "failed"]]
DOMAINS = [(d, d) for d in ["code", "social", "clinical", "diagnostic", "cad"]]
SANDBOX_STATES = [(s, s) for s in ["booting", "ready", "exited", "torn_down"]]
TOOL_STATUSES = [(s, s) for s in ["hardcoded", "fabricated_sandbox_only", "graduated"]]
ARTIFACT_KINDS = [(k, k) for k in ["pr", "social_post", "analysis", "diagnostic", "cad", "tool"]]
QUEUE_STATES = [(s, s) for s in ["pending", "approved", "rejected", "promoted"]]
CONNECTION_STATUSES = [(s, s) for s in ["active", "expired", "revoked", "pending"]]

def empty_spent():
    return {"wall_seconds": 0, "tokens": 0, "tool_calls": 0}

class Mission(models.Model):
    goal = models.TextField()
    inputs = models.JSONField(default=dict)
    success_criteria = models.TextField(blank=True)
    domain = models.CharField(max_length=32, choices=DOMAINS, default="code")
    producer_key = models.CharField(max_length=64)
    repo_url = models.TextField(blank=True)
    issue_url = models.TextField(blank=True)
    state = models.CharField(max_length=32, choices=MISSION_STATES, default="queued", db_index=True)
    state_reason = models.TextField(blank=True)
    budget = models.JSONField(default=dict)
    spent = models.JSONField(default=empty_spent)
    needs_input_prompt = models.TextField(null=True, blank=True)
    needs_input_response = models.TextField(null=True, blank=True)
    auto_act = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class Plan(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="plans")
    version = models.IntegerField(default=1)
    steps = models.JSONField(default=list)
    rendered_md = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = [("mission", "version")]

class SandboxRun(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="sandboxes")
    image_ref = models.CharField(max_length=512)
    container_id = models.CharField(max_length=128, null=True, blank=True)
    state = models.CharField(max_length=32, choices=SANDBOX_STATES, default="booting")
    log_path = models.TextField(blank=True)
    ttl_seconds = models.IntegerField(default=1800)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

class Tool(models.Model):
    name = models.CharField(max_length=128, db_index=True)
    signature = models.JSONField(default=dict)
    source_path = models.TextField()
    source_hash = models.CharField(max_length=128)
    fabricated_by_mission = models.ForeignKey(Mission, on_delete=models.SET_NULL, null=True, blank=True, related_name="fabricated_tools")
    status = models.CharField(max_length=32, choices=TOOL_STATUSES, default="hardcoded")
    created_at = models.DateTimeField(auto_now_add=True)

class Artifact(models.Model):
    mission = models.ForeignKey(Mission, on_delete=models.CASCADE, related_name="artifacts")
    producer_key = models.CharField(max_length=64)
    kind = models.CharField(max_length=32, choices=ARTIFACT_KINDS, db_index=True)
    uri = models.TextField()
    preview = models.JSONField(default=dict)
    provenance = models.JSONField(default=dict)
    validation = models.JSONField(default=dict)
    queue_state = models.CharField(max_length=32, choices=QUEUE_STATES, default="pending", db_index=True)
    tool = models.ForeignKey(Tool, on_delete=models.SET_NULL, null=True, blank=True, related_name="artifacts")
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

class Producer(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    kind = models.CharField(max_length=32, choices=ARTIFACT_KINDS)
    rubric_md = models.TextField(blank=True)
    default_budget = models.JSONField(default=dict)
    version = models.IntegerField(default=1)

class Signal(models.Model):
    source = models.CharField(max_length=32, choices=SIGNAL_SOURCES)
    external_id = models.CharField(max_length=256)
    title = models.TextField()
    payload = models.JSONField(default=dict)
    received_at = models.DateTimeField(auto_now_add=True)
    routing_status = models.CharField(max_length=32, choices=ROUTING_STATUSES, default="pending", db_index=True)
    routing_reason = models.TextField(blank=True)
    mission = models.OneToOneField(Mission, null=True, blank=True, on_delete=models.SET_NULL, related_name="signal")

    class Meta:
        unique_together = [("source", "external_id")]

class Connection(models.Model):
    """Per-toolkit OAuth state for the single shared Composio user_id."""

    toolkit = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=16, choices=CONNECTION_STATUSES, default="pending")
    composio_conn_id = models.CharField(max_length=128)
    connected_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
