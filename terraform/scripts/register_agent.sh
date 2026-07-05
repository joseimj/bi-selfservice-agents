#!/usr/bin/env bash
# Registra el Reasoning Engine como agente en Gemini Enterprise.
# Uso: register_agent.sh PROJECT GE_LOCATION AS_APP REASONING_ENGINE_ID NAME DESC
set -euo pipefail

PROJECT="$1"; GE_LOCATION="$2"; AS_APP="$3"; ENGINE_ID="$4"
NAME="$5"; DESC="$6"

if [[ "$GE_LOCATION" == "global" ]]; then
  HOST="discoveryengine.googleapis.com"
else
  HOST="${GE_LOCATION}-discoveryengine.googleapis.com"
fi

TOKEN=$(gcloud auth print-access-token)
PARENT="projects/${PROJECT}/locations/${GE_LOCATION}/collections/default_collection/engines/${AS_APP}/assistants/default_assistant"

curl -sS -X POST "https://${HOST}/v1alpha/${PARENT}/agents" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Goog-User-Project: ${PROJECT}" \
  -d @- <<JSON
{
  "displayName": "${NAME}",
  "description": "${DESC}",
  "adk_agent_definition": {
    "tool_settings": { "tool_description": "${DESC}" },
    "provisioned_reasoning_engine": {
      "reasoning_engine": "${ENGINE_ID}"
    }
  }
}
JSON
echo
echo "Agente registrado en Gemini Enterprise (app: ${AS_APP})."
