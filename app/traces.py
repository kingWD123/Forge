"""Traces Phoenix (OpenTelemetry + OpenInference) : chaque appel au modèle et à un outil,
dans l'Atelier comme dans les sous-agents, devient une étape visible dans Phoenix.

Activées par FORGE_TRACES=on. Il faut un serveur Phoenix qui écoute (par défaut
http://localhost:6006) :  .venv/Scripts/phoenix serve
FORGE_TRACES_PROJET regroupe les traces dans un projet Phoenix (ex. une campagne du banc).
Dépendances (facultatives) : opentelemetry-exporter-otlp, openinference-instrumentation-google-adk.

On n'importe pas le paquet phoenix ici : il importe jinja2 pour son serveur web, et dans le
banc le PYTHONPATH fait passer en premier le jinja2 de la tâche, parfois cassé exprès.
"""

import os

_actives = False


def activer_traces() -> bool:
    """Envoie les traces vers Phoenix si FORGE_TRACES=on. Renvoie True si elles sont actives."""
    global _actives
    if _actives or os.getenv("FORGE_TRACES", "off").lower() != "on":
        return _actives
    from openinference.instrumentation.google_adk import GoogleADKInstrumentor
    from openinference.semconv.resource import ResourceAttributes
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    fournisseur = TracerProvider(resource=Resource.create(
        {ResourceAttributes.PROJECT_NAME: os.getenv("FORGE_TRACES_PROJET", "forge-code")}))
    adresse = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006")
    # Envoi groupé, en arrière-plan.
    fournisseur.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=adresse + "/v1/traces")))
    trace.set_tracer_provider(fournisseur)
    GoogleADKInstrumentor().instrument(tracer_provider=fournisseur)
    _actives = True
    return True


def vider_traces() -> None:
    """Envoie les traces encore en attente (à appeler avant la fin d'un processus court)."""
    if not _actives:
        return
    from opentelemetry import trace

    fournisseur = trace.get_tracer_provider()
    if hasattr(fournisseur, "force_flush"):
        fournisseur.force_flush()
