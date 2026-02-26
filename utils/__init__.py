"""Utilities package — shared helpers used across all agents.

Provides the Claude API wrapper and prompt template loader that every
agent depends on for making AI calls with structured prompt templates.
"""

__all__ = [
    "claude_client",
    "prompt_loader",
]
