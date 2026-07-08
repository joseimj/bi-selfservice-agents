"""Orquestador raíz (Agent Engine, registrado en Gemini Enterprise).

Coordina especialistas remotos vía A2A: cada sub-agente vive en su propio
Cloud Run, publica su AgentCard en /.well-known/agent-card.json y el
orquestador los consume como RemoteA2aAgent (sub_agents del ADK).
"""
import os

from google.adk.agents import LlmAgent
from google.adk.agents.remote_a2a_agent import (
    AGENT_CARD_WELL_KNOWN_PATH,
    RemoteA2aAgent,
)

from common.model_factory import get_model
from orchestrator.a2ui_prompt import build_instruction


def _remote(name: str, env_url: str, description: str) -> RemoteA2aAgent:
    base = os.environ[env_url].rstrip("/")
    return RemoteA2aAgent(
        name=name,
        description=description,
        agent_card=f"{base}{AGENT_CARD_WELL_KNOWN_PATH}",
    )


catalog = _remote(
    "looker_catalog_agent", "CATALOG_AGENT_URL",
    "Descubre modelos, explores y campos LookML; valida campos y hace previews de queries.",
)
builder = _remote(
    "looker_dashboard_builder", "BUILDER_AGENT_URL",
    "Crea dashboards nativos en Looker: tiles, filtros cross-tile y layout.",
)
renderer = _remote(
    "looker_render_agent", "RENDER_AGENT_URL",
    "Renderiza dashboards como imagen inline y genera links SSO firmados.",
)

sub_agents = [catalog, builder, renderer]
if os.environ.get("EXCEL_AGENT_URL"):
    sub_agents.append(_remote(
        "looker_excel_agent", "EXCEL_AGENT_URL",
        "Genera archivos Excel (.xlsx) con formato a partir de queries de Looker "
        "o de dashboards existentes; entrega por URL firmada de descarga.",
    ))

BASE_INSTRUCTION = """Flujo de autoservicio (siempre en este orden):

1. ENTENDER: extrae del usuario el objetivo del dashboard (tema, métricas, cortes,
   filtros, número de tiles). Si falta información, pregunta UNA vez de forma concreta.

2. TEMPLATES PRIMERO (delega a looker_catalog_agent): consulta
   list_dashboard_templates; si la petición encaja con un template organizacional,
   propónlo ANTES que un diseño desde cero (consistencia > creatividad). Pide al
   usuario solo los parámetros que el template declare y valida cada campo con el
   Catalog. Diseña desde cero solo si ningún template aplica o el usuario lo pide.

3. DESCUBRIR (delega a looker_catalog_agent): resuelve modelo/explore y obtén los
   nombres EXACTOS view.field de dimensiones y medidas. Pide un preview_query de al
   menos un tile para validar el spec antes de construir.

4. PROPONER: presenta el DashboardSpec (título, tiles con campos y tipo de gráfico,
   filtros, layout) y espera confirmación del usuario.

5. CONSTRUIR (delega a looker_dashboard_builder): con template usa create_dashboard_from_template(template_id, params); sin template, el spec confirmado.
   Recibe dashboard_id y url.

6. VERIFICAR Y ENTREGAR (delega a looker_render_agent): pide el render inline para
   que el usuario lo vea, y el link SSO firmado para abrirlo interactivo.

7. EXPORTAR (opcional, delega a looker_excel_agent si está disponible): si el
   usuario pide el resultado "en Excel" o un entregable offline, exporta el
   dashboard recién creado (export_dashboard_to_excel) o los queries validados
   (export_query_to_excel / export_multi_sheet_excel) y comparte la URL firmada.

Reglas:
- Nunca inventes nombres de campos: solo los que devuelva el Catalog Agent.
- Operaciones destructivas (borrar) requieren confirmación explícita.
- Responde en el idioma del usuario. Reporta siempre dashboard_id y url final.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_selfservice_orchestrator",
    description=(
        "Orquestador de autoservicio analítico: crea dashboards nativos de Looker "
        "a partir de lenguaje natural coordinando agentes especialistas por A2A."
    ),
    instruction=build_instruction(BASE_INSTRUCTION),
    sub_agents=sub_agents,
)
