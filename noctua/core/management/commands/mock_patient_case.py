"""Patient case → clinical_analysis mission.

  ./manage.py mock_patient_case                                    # random sample
  ./manage.py mock_patient_case --sample-index 2
  ./manage.py mock_patient_case 67 year old with sudden left-sided weakness, BP 192/110
"""
from noctua.core.management.commands._mock_alias import MockAliasCommand


class Command(MockAliasCommand):
    kind = "clinical"
    help = "Mock a clinical case (kind=clinical → clinical_analysis producer)."
