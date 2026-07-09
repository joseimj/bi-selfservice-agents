"""Deliverables Agent: orquestador intermedio de la subcuadrilla de formatos.

Recibe la intención de entregable ("mándamelo en Excel/slides/Word/PDF/CSV")
y delega vía A2A al especialista de formato. No genera archivos por sí mismo:
su único trabajo es enrutar bien y consolidar la respuesta (download_url).
"""
import os

from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)

from common.model_factory import get_model


def _remote(name: str, env_url: str, description: str) -> RemoteA2aAgent:
    base = os.environ[env_url].rstrip("/")
    return RemoteA2aAgent(name=name, description=description,
                          agent_card=f"{base}{AGENT_CARD_WELL_KNOWN_PATH}")


tabular = _remote(
    "looker_excel_agent", "EXCEL_AGENT_URL",
    "Datos tabulares: workbooks .xlsx con formato (query, multi-hoja o dashboard "
    "completo) y CSV plano para intercambio con sistemas.",
)
slides = _remote(
    "looker_slides_agent", "SLIDES_AGENT_URL",
    "Presentaciones .pptx: portada + una lámina por tile del dashboard, con "
    "template corporativo opcional.",
)
docs = _remote(
    "looker_docs_agent", "DOCS_AGENT_URL",
    "Documentos Word .docx: reporte por tiles (imagen + muestra de datos) o "
    "documento narrativo por secciones.",
)
pdf = _remote(
    "looker_pdf_agent", "PDF_AGENT_URL",
    "PDF: render nativo del dashboard por Looker (default) o documento "
    "compuesto a la medida con portada, secciones y anexo gráfico.",
)
data = _remote(
    "looker_data_exports_agent", "DATA_AGENT_URL",
    "Formatos machine-readable para sistemas: JSON, Parquet y Avro con esquema "
    "de tipos derivado de LookML.",
)

INSTRUCTION = """Eres el Deliverables Agent: la puerta única de la subcuadrilla de
formatos. Tu trabajo es ENRUTAR, no generar.

Mapa de enrutamiento:
- "excel", "xlsx", "hoja de cálculo", datos con formato -> looker_excel_agent
- "csv", "para cargar en otro sistema" -> looker_excel_agent (tool CSV)
- "presentación", "slides", "ppt", "para presentar al comité" -> looker_slides_agent
- "word", "docx", "documento", "reporte escrito" -> looker_docs_agent
- "pdf" -> looker_pdf_agent (ruta nativa por defecto; compuesta solo si piden
  portada/narrativa a la medida)
- "json", "parquet", "avro", "para el data lake", "para consumir desde otro
  sistema" -> looker_data_exports_agent (CSV simple sigue en looker_excel_agent)

Reglas:
- Si el formato es ambiguo ("mándamelo", "expórtalo"), pregunta UNA vez con las
  opciones disponibles; no adivines.
- Pasa íntegros dashboard_id, campos ya validados, template_name y filtros.
- Si piden varios formatos a la vez, delega a cada especialista y consolida
  todas las download_url en una sola respuesta.
- Devuelve SIEMPRE download_url y expiración por cada entregable.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_deliverables_agent",
    description=(
        "Puerta única de entregables: enruta peticiones de exportación a los "
        "especialistas de formato (Excel/CSV, Slides, Word, PDF) y consolida "
        "las URLs firmadas de descarga."
    ),
    instruction=INSTRUCTION,
    sub_agents=[tabular, slides, docs, pdf, data],
)
