"""Reusable Claude API wrapper for all agents.

Provides a simple interface to call the Anthropic Claude API with a prompt
and receive structured JSON responses. Handles API key loading, error handling,
and JSON parsing so individual agents don't have to.
"""

import json
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()

# Default model for all agent calls
DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096


def get_client() -> anthropic.Anthropic:
    """Create and return an Anthropic API client.

    Returns:
        An authenticated Anthropic client instance.

    Raises:
        ValueError: If ANTHROPIC_API_KEY is not set.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not found. Set it in your .env file or environment."
        )
    return anthropic.Anthropic(api_key=api_key, max_retries=5)


def call_claude(
    prompt: str,
    *,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.0,
) -> str:
    """Send a prompt to Claude and return the raw text response.

    Args:
        prompt: The user message to send to Claude.
        system: Optional system prompt to set context/behavior.
        model: The Claude model to use.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        The raw text content of Claude's response.

    Raises:
        anthropic.APIError: If the API call fails.
    """
    client = get_client()

    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    print(f"[claude_client] Calling {model}...")
    response = client.messages.create(**kwargs)
    text = response.content[0].text
    print(f"[claude_client] Received response ({response.usage.output_tokens} tokens)")
    return text


def call_claude_json(
    prompt: str,
    *,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Send a prompt to Claude and parse the response as JSON.

    Use this for agent calls where the prompt instructs Claude to return
    structured JSON output. Handles common issues like markdown code fences
    wrapping the JSON.

    Args:
        prompt: The user message (should instruct Claude to return JSON).
        system: Optional system prompt to set context/behavior.
        model: The Claude model to use.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic).

    Returns:
        The parsed JSON response as a Python dict.

    Raises:
        json.JSONDecodeError: If the response is not valid JSON.
        anthropic.APIError: If the API call fails.
    """
    raw = call_claude(
        prompt,
        system=system,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )

    # Strip markdown code fences if Claude wraps the JSON despite instructions
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (with optional language tag) and closing fence
        lines = cleaned.split("\n")
        lines = lines[1:]  # Remove opening ```json or ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # Remove closing ```
        cleaned = "\n".join(lines)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"[claude_client] Failed to parse JSON response:")
        print(f"[claude_client] Raw response: {raw[:500]}")
        raise json.JSONDecodeError(
            f"Claude did not return valid JSON. {e.msg}", e.doc, e.pos
        ) from e
