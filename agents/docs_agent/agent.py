from google.adk.agents import LlmAgent

from common.model_factory import get_model
from docs_agent.tools import ALL_TOOLS

INSTRUCTION = """Eres el agente de DOCS de la subcuadrilla de deliverables: produces
documentos Word desde contenido de Looker.

- export_dashboard_to_docx: reporte con una sección por tile (imagen + muestra
  de datos). Acepta template_name (.docx corporativo).
- create_document: documento narrativo por secciones {"heading","body"} — las
  cifras del cuerpo deben venir de queries validados, nunca inventadas.
- list_docs_templates: templates corporativos disponibles.

Devuelve SIEMPRE la download_url y su expiración.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_docs_agent",
    description=(
        "Genera documentos Word (.docx) desde dashboards (sección por tile con imagen y muestra de datos) o documentos narrativos por secciones; entrega por URL firmada."
    ),
    instruction=INSTRUCTION,
    tools=ALL_TOOLS,
)
