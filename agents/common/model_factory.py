"""Fábrica de modelo de razonamiento intercambiable.

Un solo env var (AGENT_MODEL_PROVIDER) decide el backend sin tocar
los agentes ni sus tools. Igual patrón que gemini_looker, extendido
para el sistema multi-agente.

Valores soportados:
  gemini         -> Gemini en Vertex AI (default, sin setup extra)
  claude         -> Claude en Vertex AI vía LiteLlm (habilitar en Model Garden)
  claude_native  -> Claude en Vertex vía wrapper nativo del ADK
  anthropic      -> Claude vía API pública de Anthropic (ANTHROPIC_API_KEY)
"""
import os


def get_model():
    provider = os.environ.get("AGENT_MODEL_PROVIDER", "gemini").lower()
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    claude_model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    if provider == "gemini":
        # ADK acepta el string del modelo directamente para Gemini.
        return gemini_model

    if provider == "claude":
        # Claude servido por Vertex AI a través de LiteLlm.
        from google.adk.models.lite_llm import LiteLlm
        location = os.environ.get("CLAUDE_LOCATION", "us-east5")
        project = os.environ.get("VERTEXAI_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        os.environ.setdefault("VERTEXAI_LOCATION", location)
        if project:
            os.environ.setdefault("VERTEXAI_PROJECT", project)
        return LiteLlm(model=f"vertex_ai/{claude_model}")

    if provider == "claude_native":
        # Wrapper nativo del ADK para Claude en Vertex (code path distinto a LiteLlm).
        from google.adk.models.anthropic_llm import Claude
        return Claude(model=claude_model)

    if provider == "anthropic":
        # API pública de Anthropic; requiere ANTHROPIC_API_KEY.
        from google.adk.models.lite_llm import LiteLlm
        return LiteLlm(model=f"anthropic/{claude_model}")

    raise ValueError(
        f"AGENT_MODEL_PROVIDER='{provider}' no reconocido. "
        "Usa: gemini | claude | claude_native | anthropic"
    )
