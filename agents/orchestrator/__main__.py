"""Superficie A2A+A2UI del orquestador (opcional, Cloud Run).

Gemini Enterprise consume el orquestador vía Agent Engine (deploy.py /
Terraform). Esta superficie adicional lo expone como servidor A2A cuyo
AgentCard anuncia la extensión A2UI, para que un frontend con renderer
(Lit/Angular/Flutter) muestre wizards y previews como UI nativa.
"""
import os

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from orchestrator.agent import root_agent

PORT = int(os.environ.get("PORT", 8080))
PUBLIC_URL = os.environ.get("PUBLIC_URL", f"http://localhost:{PORT}")

a2a_app = to_a2a(root_agent, host="0.0.0.0", port=PORT, protocol="http")

if hasattr(a2a_app, "agent_card") and a2a_app.agent_card:
    a2a_app.agent_card.url = PUBLIC_URL
    # Anunciar la capacidad A2UI en el AgentCard (descubrible por el frontend).
    try:
        from a2ui.a2a import get_a2ui_agent_extension
        caps = a2a_app.agent_card.capabilities
        caps.extensions = (caps.extensions or []) + [
            get_a2ui_agent_extension(supported_catalog_ids=["a2ui.org/basic"])
        ]
    except ImportError:
        pass

if __name__ == "__main__":
    uvicorn.run(a2a_app, host="0.0.0.0", port=PORT)
