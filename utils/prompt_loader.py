"""Prompt template loader and variable substitution.

Loads markdown prompt templates from the /prompts/ directory and populates
{{variable_name}} placeholders with provided values. This keeps prompt
engineering separate from agent logic.
"""

import re
from pathlib import Path

# Resolve the prompts directory relative to this file's location
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(template_name: str, **variables: str) -> str:
    """Load a prompt template and substitute variables.

    Templates live in the /prompts/ directory as markdown files with
    {{variable_name}} placeholders. All placeholders in the template
    must be provided as keyword arguments.

    Args:
        template_name: Filename of the template (e.g. "content_brief_template.md").
        **variables: Key-value pairs to substitute into the template.
            Keys should match placeholder names without the curly braces.

    Returns:
        The fully populated prompt string ready to send to Claude.

    Raises:
        FileNotFoundError: If the template file does not exist.
        ValueError: If the template contains placeholders not provided in variables.

    Example:
        >>> prompt = load_prompt(
        ...     "content_brief_template.md",
        ...     query="python async tutorial",
        ...     impressions="4500",
        ... )
    """
    template_path = PROMPTS_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(
            f"Prompt template not found: {template_path}. "
            f"Available templates: {list_templates()}"
        )

    template = template_path.read_text(encoding="utf-8")

    # Find all placeholders in the template
    placeholders = set(re.findall(r"\{\{(\w+)\}\}", template))

    # Check for missing variables
    provided = set(variables.keys())
    missing = placeholders - provided
    if missing:
        raise ValueError(
            f"Missing variables for template '{template_name}': {missing}. "
            f"Template expects: {placeholders}"
        )

    # Warn about extra variables (not an error, just informational)
    extra = provided - placeholders
    if extra:
        print(f"[prompt_loader] Warning: extra variables ignored for '{template_name}': {extra}")

    # Substitute all placeholders
    populated = template
    for key, value in variables.items():
        populated = populated.replace(f"{{{{{key}}}}}", str(value))

    return populated


def list_templates() -> list[str]:
    """List all available prompt template filenames.

    Returns:
        A sorted list of .md filenames in the prompts directory.
    """
    if not PROMPTS_DIR.exists():
        return []
    return sorted(f.name for f in PROMPTS_DIR.glob("*.md"))
