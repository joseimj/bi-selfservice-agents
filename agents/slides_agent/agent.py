from google.adk.agents import LlmAgent

from common.model_factory import get_model
from slides_agent.tools import ALL_TOOLS

INSTRUCTION = """Eres el agente de SLIDES de la subcuadrilla de deliverables: produces
presentaciones .pptx desde dashboards de Looker.

- export_dashboard_to_slides: portada + una lámina por tile (visualización
  renderizada como imagen). Acepta template_name (.pptx corporativo).
- list_slides_templates: templates corporativos disponibles.

Reglas: si el usuario menciona un template o existe uno corporativo, úsalo.
Reporta tiles omitidos si alguno no renderiza. Devuelve SIEMPRE la
download_url y su expiración. No describas lámina por lámina en texto.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_slides_agent",
    description=(
        "Genera presentaciones .pptx desde dashboards de Looker (una lámina por tile, portada, template corporativo); entrega por URL firmada."
    ),
    instruction=INSTRUCTION,
    tools=ALL_TOOLS,
)
