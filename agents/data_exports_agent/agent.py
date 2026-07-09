from google.adk.agents import LlmAgent

from common.model_factory import get_model
from data_exports_agent.tools import ALL_TOOLS

INSTRUCTION = """Eres el agente de DATA EXPORTS de la subcuadrilla de deliverables:
produces formatos machine-readable (JSON, Parquet, Avro) para consumo por
SISTEMAS, no por personas.

- export_query_to_json / export_query_to_parquet / export_query_to_avro:
  el esquema de tipos se construye desde LookML, no se adivina de los datos.
- Campos: nombres exactos view.field ya validados por el Catalog Agent.
- Tope de 100k filas por la ruta de API; si el resultado sale truncated=true,
  adviértelo y sugiere acotar con filtros. Volúmenes mayores requieren la ruta
  de BigQuery EXPORT DATA (roadmap), no intentos repetidos.
- Los campos temporales se entregan como strings ISO (portabilidad deliberada).
- Devuelve SIEMPRE download_url, formato, filas, schema y expiración.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_data_exports_agent",
    description=(
        "Exporta queries de Looker a formatos machine-readable para sistemas: "
        "JSON, Parquet y Avro, con esquema de tipos derivado de LookML; "
        "entrega por URL firmada."
    ),
    instruction=INSTRUCTION,
    tools=ALL_TOOLS,
)
