"""FORGE CODE : agent de code en terminal qui forge ses propres sous-agents."""

import os

import google.auth
from dotenv import load_dotenv

load_dotenv()

# Vertex AI : si .env ne fixe pas le projet, on prend celui des identifiants gcloud (ADC).
try:
    _, project_id = google.auth.default()
    if project_id:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
except google.auth.exceptions.DefaultCredentialsError:
    pass

# Traces Phoenix (FORGE_TRACES=on), avant de construire les agents.
from .traces import activer_traces  # noqa: E402

activer_traces()

from . import agent  # noqa: E402 -- doit venir après load_dotenv()

__all__ = ["agent"]
