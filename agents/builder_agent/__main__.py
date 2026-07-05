"""Expone el agente como servidor A2A (Cloud Run)."""
import os

import uvicorn
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from builder_agent.agent import root_agent

PORT = int(os.environ.get("PORT", 8080))
PUBLIC_URL = os.environ.get("PUBLIC_URL", f"http://localhost:{PORT}")

a2a_app = to_a2a(root_agent, host="0.0.0.0", port=PORT, protocol="http")
if hasattr(a2a_app, "agent_card") and a2a_app.agent_card:
    a2a_app.agent_card.url = PUBLIC_URL

if __name__ == "__main__":
    uvicorn.run(a2a_app, host="0.0.0.0", port=PORT)
