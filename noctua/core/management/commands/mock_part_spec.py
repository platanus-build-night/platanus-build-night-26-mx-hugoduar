"""CAD part request → cad mission.

  ./manage.py mock_part_spec                                       # random sample
  ./manage.py mock_part_spec --sample-index 1
  ./manage.py mock_part_spec Design a wall mount for a 27in monitor with VESA 100
"""
from noctua.core.management.commands._mock_alias import MockAliasCommand


class Command(MockAliasCommand):
    kind = "cad"
    help = "Mock a CAD spec request (kind=cad → cad producer)."
