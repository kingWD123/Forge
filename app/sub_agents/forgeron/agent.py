"""Forgeron : conçoit un sous-agent spécialisé au format Agent Config YAML."""

import os

from google.adk.agents import LlmAgent

from . import prompt

forgeron_agent = LlmAgent(
    model=os.getenv("MODEL_NAME", "gemini-2.5-flash"),
    name="forgeron_agent",
    description="Conçoit un sous-agent spécialisé (Agent Config YAML) pour une tâche.",
    instruction=prompt.FORGERON_PROMPT,
)
