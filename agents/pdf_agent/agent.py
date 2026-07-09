from google.adk.agents import LlmAgent

from common.model_factory import get_model
from pdf_agent.tools import ALL_TOOLS

INSTRUCTION = """Eres el agente de PDF de la subcuadrilla de deliverables.

Dos rutas, en este orden de preferencia:
1. export_dashboard_to_pdf (NATIVA): para "el dashboard en PDF". Fiel al
   layout de Looker, sin composición. Úsala por defecto.
2. compose_pdf_document (COMPUESTA): solo para documentos a la medida
   (portada + secciones narrativas + anexo gráfico opcional de un dashboard).

Devuelve SIEMPRE la download_url y su expiración.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_pdf_agent",
    description=(
        "Genera PDFs: dashboard renderizado nativamente por Looker (ruta por defecto) o documento compuesto a la medida con portada, secciones y anexo gráfico; entrega por URL firmada."
    ),
    instruction=INSTRUCTION,
    tools=ALL_TOOLS,
)
