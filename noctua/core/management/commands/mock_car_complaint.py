"""Mechanic intake → diagnostic mission.

  ./manage.py mock_car_complaint                                   # random sample
  ./manage.py mock_car_complaint --sample-index 3
  ./manage.py mock_car_complaint 2012 Subaru Outback grinding noise on left turns above 30mph
"""
from noctua.core.management.commands._mock_alias import MockAliasCommand


class Command(MockAliasCommand):
    kind = "diagnostic"
    help = "Mock a vehicle complaint (kind=diagnostic → diagnostic producer)."
