"""Tool fabrication request → sandbox-only tool artifact.

  ./manage.py mock_tool_idea                                       # random sample
  ./manage.py mock_tool_idea --sample-index 0
  ./manage.py mock_tool_idea Build a tool that converts a CSV to a SQL CREATE TABLE statement
"""
from noctua.core.management.commands._mock_alias import MockAliasCommand


class Command(MockAliasCommand):
    kind = "tool"
    help = "Mock a tool-fabrication request (kind=tool → tool_demo producer)."
