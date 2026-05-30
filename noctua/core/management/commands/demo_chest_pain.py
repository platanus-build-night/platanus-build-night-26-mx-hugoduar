"""Pre-baked demo: ER intake → clinical_analysis artifact.

  ./manage.py demo_chest_pain
"""
from django.core.management.base import BaseCommand

from noctua.signals.mock import build_payload, post_signal


TITLE = "ER intake — 54M acute chest pain"
GOAL = (
    "Patient: 54-year-old male, walked into the ED 90 minutes after onset of "
    "substernal chest pressure radiating to the left arm and jaw. Pain 8/10, "
    "diaphoretic, mildly short of breath. Vitals: HR 102, BP 158/94, RR 20, "
    "SpO2 97% on room air, afebrile. PMH: hypertension on lisinopril, "
    "hyperlipidemia on atorvastatin, current smoker (1 ppd × 30 years). "
    "12-lead ECG shows 2mm ST elevation in leads II, III, aVF with reciprocal "
    "depression in I and aVL. Initial troponin: pending.\n\n"
    "Produce: a structured clinical summary including (a) the most likely "
    "diagnosis with supporting evidence, (b) the immediate next steps in the "
    "next 10 minutes, (c) the relevant differential, and (d) the disposition. "
    "Tone: concise, what an attending would hand off to a fellow."
)


class Command(BaseCommand):
    help = "Demo: clinical analysis — STEMI workup for an ER chest-pain case."

    def handle(self, *args, **opts):
        payload = build_payload(kind="clinical", title=TITLE, goal=GOAL)
        post_signal(payload, stdout=self.stdout, style=self.style)
