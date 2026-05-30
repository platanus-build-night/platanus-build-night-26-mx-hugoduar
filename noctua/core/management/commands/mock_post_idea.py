"""Social post idea → social_post mission.

  ./manage.py mock_post_idea                                       # random sample
  ./manage.py mock_post_idea --sample-index 0
  ./manage.py mock_post_idea Tweet about the new mock_signal CLI
"""
from noctua.core.management.commands._mock_alias import MockAliasCommand


class Command(MockAliasCommand):
    kind = "social"
    help = "Mock a social-post request (kind=social → social_post producer)."
