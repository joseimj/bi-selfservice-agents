import base64
import json

from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext
from google.genai import types as genai_types

from common.model_factory import get_model
from render_agent.tools import render_dashboard_png, get_signed_embed_url


async def show_dashboard_inline(dashboard_id: str, tool_context: ToolContext) -> str:
    """Renderiza el dashboard y lo guarda como artifact ADK (imagen inline en el chat).

    Los bytes del PNG NUNCA pasan por el texto del modelo: se guardan como
    artifact y el runtime los muestra nativamente (único enfoque confiable en GE).
    """
    result = render_dashboard_png(dashboard_id)
    if result.get("status") != "ok":
        return json.dumps(result)
    png_bytes = base64.b64decode(result["png_base64"])
    filename = f"dashboard_{dashboard_id}.png"
    await tool_context.save_artifact(
        filename=filename,
        artifact=genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png"),
    )
    return json.dumps({"status": "ok", "artifact": filename,
                       "note": "imagen guardada como artifact, mostrada inline"})


INSTRUCTION = """Eres el Render & QA Agent de Looker.

- show_dashboard_inline: renderiza un dashboard como PNG y lo muestra inline
  (artifact ADK). Úsalo para que el usuario verifique visualmente lo construido.
- get_signed_embed_url: genera el link interactivo firmado (SSO embed).

Después de renderizar, reporta si el dashboard se ve completo (tiles, títulos).
El link firmado se genera en una tool separada: nunca bloquea al render.
"""

root_agent = LlmAgent(
    model=get_model(),
    name="looker_render_agent",
    description="Renderiza dashboards de Looker como imagen inline y genera links SSO firmados.",
    instruction=INSTRUCTION,
    tools=[show_dashboard_inline, get_signed_embed_url],
)
