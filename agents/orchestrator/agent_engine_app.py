"""Entrypoint para Vertex AI Agent Engine (superficie Gemini Enterprise).

Terraform empaqueta agents/ como tar.gz base64 y lo despliega con
google_vertex_ai_reasoning_engine; esta variable `agent_engine` es la
que el runtime instancia (class_methods: stream_query).
"""
from vertexai.preview import reasoning_engines

from orchestrator.agent import root_agent

agent_engine = reasoning_engines.AdkApp(agent=root_agent, enable_tracing=False)
