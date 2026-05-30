"""Shared helpers for the mock_* management commands.

Holds the sample fixtures and the wire call to POST /api/signals/mock,
so the per-kind convenience commands (mock_feature_request, mock_post_idea,
mock_patient_case, ...) and the generic mock_signal command stay in sync.
"""
import json
import os
import random
import string


DEFAULT_REPO = "https://github.com/hugoduar/noctua-demo-app"


# (title, goal) tuples per kind. Keep these short and demo-friendly.
SAMPLES: dict[str, list[tuple[str, str]]] = {
    "code": [
        (
            "Add a /health endpoint",
            "Add a GET /health endpoint to the FastAPI app in src/app.py that returns {\"status\": \"ok\"}. Include a test.",
        ),
        (
            "Log request ids",
            "Add request-id logging middleware to src/app.py — read X-Request-Id from the header or generate a uuid, attach it to every log line.",
        ),
        (
            "Pin dependency versions",
            "Pin top-level pinned versions in requirements.txt for reproducible installs.",
        ),
    ],
    "tool": [
        (
            "Fabricate: csv_to_markdown",
            "Build a sandbox-only tool that converts a CSV string into a GitHub-flavored markdown table.",
        ),
        (
            "Fabricate: slug_from_title",
            "Build a sandbox-only tool that turns a free-form title into a URL-safe slug (lowercase, hyphenated, ascii).",
        ),
        (
            "Fabricate: word_count",
            "Build a sandbox-only tool that returns word and character counts for a given text blob.",
        ),
    ],
    "social": [
        ("Launch tweet — overnight artifact factory",
         "Draft a launch tweet (≤280 chars) for Noctua: overnight artifact factory, mission in → PR / post / analysis out."),
        ("Thread — why we built Noctua",
         "Draft a 5-tweet thread on why we built Noctua. Voice: technical founder, no marketing fluff."),
        ("LinkedIn — hiring engineer",
         "Draft a LinkedIn post announcing a senior engineer opening on the Noctua team. Tone: candid, no buzzwords."),
        ("Tweet — sandboxed code execution",
         "Draft a tweet explaining why every Noctua mission runs in a Docker sandbox. Make it concrete."),
    ],
    "clinical": [
        ("Chest pain — 54M",
         "54-year-old male, 2 hours of substernal chest pressure radiating to left arm, diaphoretic, HR 102, BP 158/94. Past hx: HTN, hyperlipidemia, smoker. ECG shows ST elevation in II, III, aVF. Summarize differential and immediate next steps."),
        ("Pediatric fever — 3yo",
         "3-year-old female, 3 days fever to 39.5°C, decreased PO intake, no rash, no cough. Exam: erythematous oropharynx, no exudate, no LAD. Outline likely causes and red flags."),
        ("Postpartum dyspnea",
         "32-year-old female, 6 days postpartum (uncomplicated vaginal delivery), now with acute dyspnea, pleuritic chest pain, HR 118, SpO2 91%. List differential and urgent workup."),
        ("Lab review — abnormal TSH",
         "Asymptomatic 41-year-old female: TSH 8.4 (high), free T4 within range. Discuss next steps and whether to treat."),
    ],
    "diagnostic": [
        ("2019 Honda Civic — squeal on brake",
         "2019 Honda Civic, 78k miles. High-pitched squeal when braking at low speed, intermittent. No pulling, no pedal vibration. Pads were replaced 8 months ago."),
        ("2014 Ford F-150 — rough idle",
         "2014 Ford F-150 5.0L, 132k miles. Rough idle when cold, smooths out after 5 minutes. Slight loss of power on hills. No CEL."),
        ("2008 BMW 328i — overheating",
         "2008 BMW 328i. Engine temp climbs above normal during highway driving in summer; returns to normal at idle. Coolant level dropped slightly over 2 weeks. No visible leaks."),
        ("2017 Toyota Tacoma — vibration at 65mph",
         "2017 Toyota Tacoma. Steering wheel vibration starting around 60 mph, peaks at 65, smooths out above 75. Tires rotated and balanced last week."),
    ],
    "cad": [
        ("Parametric wall bracket",
         "Specify a parametric L-bracket for mounting a 5kg shelf to drywall. Parameters: shelf depth, load rating, mounting hole pattern. Output: STEP-friendly geometric spec."),
        ("GoPro handlebar mount",
         "Specify a GoPro mount that clamps to a 31.8mm bike handlebar. Material: PETG. Include screw spec and printable orientation guidance."),
        ("Raspberry Pi 5 case — fanless",
         "Specify a fanless aluminum case for Raspberry Pi 5 acting as heatsink. Cutouts for USB-C, micro-HDMI ×2, GPIO header."),
        ("Cable pass-through grommet — desk",
         "Specify a 60mm desk grommet with brush insert, fits 18mm desk thickness. Include tolerances for press-fit."),
    ],
}


def pick_sample(kind: str, sample_index: int | None) -> tuple[str, str]:
    """Resolve (title, goal) from the sample list. If sample_index is None,
    a random sample is chosen; otherwise we modulo into the list so the index
    is always valid (callers passing -1 or 99 just wrap)."""
    samples = SAMPLES[kind]
    if sample_index is None:
        return random.choice(samples)
    return samples[sample_index % len(samples)]


def random_external_id() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=10))


def build_payload(
    *,
    kind: str,
    goal: str,
    title: str,
    external_id: str | None = None,
    repo_url: str | None = None,
    issue_url: str = "",
) -> dict:
    payload = {
        "kind": kind,
        "external_id": external_id or random_external_id(),
        "title": title,
        "goal": goal,
        "inputs": {},
    }
    if kind == "code":
        payload["repo_url"] = repo_url or DEFAULT_REPO
        if issue_url:
            payload["issue_url"] = issue_url
    return payload


def post_signal(payload: dict, stdout=None, style=None) -> dict:
    """POST the payload to /api/signals/mock and return the JSON body."""
    import httpx

    api_url = os.environ.get("NOCTUA_API_URL", "http://127.0.0.1:8000")
    token = os.environ.get("NOCTUA_API_TOKEN", "")

    if stdout is not None:
        notice = style.NOTICE if style else (lambda s: s)
        success = style.SUCCESS if style else (lambda s: s)
        stdout.write(notice(f"POST {api_url}/api/signals/mock"))
        stdout.write(json.dumps(payload, indent=2))

    r = httpx.post(
        f"{api_url}/api/signals/mock",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()

    if stdout is not None:
        stdout.write(success(f"\nResponse: {r.status_code}"))
        stdout.write(json.dumps(body, indent=2))
    return body
