"""Feature request → code (PR) mission.

  ./manage.py mock_feature_request                                # random sample
  ./manage.py mock_feature_request --sample-index 1
  ./manage.py mock_feature_request Add a /metrics endpoint with prometheus output
  ./manage.py mock_feature_request --repo-url https://github.com/me/myrepo \
      Fix the off-by-one in the pagination helper
"""
from noctua.core.management.commands._mock_alias import MockCodeAliasCommand


class Command(MockCodeAliasCommand):
    help = "Mock a feature-request signal (kind=code → pr producer)."
