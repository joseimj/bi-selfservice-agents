#!/usr/bin/env python3
"""Fallback de deploy del orquestador a Agent Engine vía SDK de Vertex.

Úsalo si tu versión del provider google-beta aún no soporta el empaquetado
de fuente ADK en google_vertex_ai_reasoning_engine:

  python3 deploy_agent_engine.py --project P --region R --bucket B [--engine-id ID]

Crea (o actualiza) el AdkApp del orquestador y escribe el resource name en
.build/engine_id.txt para que Terraform lo consuma (data.local_file).
"""
import argparse
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "agents"))

import vertexai
from vertexai import agent_engines
from vertexai.preview import reasoning_engines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--region", required=True)
    ap.add_argument("--bucket", required=True)
    ap.add_argument("--engine-id", default="")
    args = ap.parse_args()

    vertexai.init(project=args.project, location=args.region,
                  staging_bucket=f"gs://{args.bucket}")

    from orchestrator.agent import root_agent
    app = reasoning_engines.AdkApp(agent=root_agent, enable_tracing=False)

    env_keys = ["AGENT_MODEL_PROVIDER", "GEMINI_MODEL", "CLAUDE_MODEL",
                "CLAUDE_LOCATION", "VERTEXAI_PROJECT", "VERTEXAI_LOCATION",
                "LOOKERSDK_BASE_URL", "LOOKERSDK_CLIENT_ID", "LOOKERSDK_CLIENT_SECRET",
                "LOOKER_MODELS", "LOOKER_TARGET_FOLDER_ID", "A2UI_ENABLED",
                "CATALOG_AGENT_URL", "BUILDER_AGENT_URL", "RENDER_AGENT_URL"]
    env_vars = {k: os.environ[k] for k in env_keys if os.environ.get(k)}

    reqs = (pathlib.Path(__file__).resolve().parents[2]
            / "agents/orchestrator/requirements.txt").read_text().splitlines()

    kwargs = dict(
        agent_engine=app,
        display_name="looker-selfservice-orchestrator",
        requirements=[r for r in reqs if r.strip()],
        extra_packages=["common", "orchestrator"],
        env_vars=env_vars,
    )
    if args.engine_id:
        engine = agent_engines.update(resource_name=args.engine_id, **kwargs)
    else:
        engine = agent_engines.create(**kwargs)

    out = pathlib.Path(__file__).resolve().parents[1] / ".build"
    out.mkdir(exist_ok=True)
    (out / "engine_id.txt").write_text(engine.resource_name)
    print(engine.resource_name)


if __name__ == "__main__":
    main()
