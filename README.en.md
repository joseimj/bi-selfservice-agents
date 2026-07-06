# bi-selfservice-agents

[Español](README.md) | **English** | [Français](README.fr.md) | [Português](README.pt.md)

**Next-level analytics self-service: a multi-agent system (ADK + A2A + A2UI) that CREATES native Looker dashboards from natural language, deployable end-to-end with Terraform on GCP and registered in Gemini Enterprise.**

The leap beyond the usual "agent that renders images" pattern: here, the outcome of every conversation is a real user-defined dashboard in Looker (tiles with queries, cross-tile filters, layout), editable and governed by LookML.

---

## Architecture

```
                         ┌────────────────────────────┐
   Surface 1             │      Gemini Enterprise      │  text + inline images
   (employees)           └──────────────┬─────────────┘  (artifacts) + SSO links
                                        │
                          ┌─────────────▼──────────────┐
                          │  Vertex AI Agent Engine     │
                          │  ORCHESTRATOR (ADK LlmAgent)│  swappable model:
                          │  looker_selfservice_        │  gemini | claude |
                          │  orchestrator               │  claude_native | anthropic
                          └───────┬──────────┬─────────┘
   Surface 2                      │   A2A    │   A2A (AgentCards at
   (custom frontend)              │ (JSON-RPC│    /.well-known/agent-card.json)
 ┌──────────────────┐             │  /HTTP)  │
 │ A2UI frontend    │   A2A +     │          │
 │ (Lit/Angular/    │◄──A2UI──────┤          │
 │  Flutter)        │  DataPart   │          │
 └──────────────────┘  json+a2ui  │          │
                     ┌────────────▼──┐  ┌────▼──────────┐  ┌───────────────┐
                     │ CATALOG AGENT │  │ BUILDER AGENT │  │ RENDER AGENT  │
                     │ (Cloud Run)   │  │ (Cloud Run)   │  │ (Cloud Run)   │
                     │ models,       │  │ create_dash,  │  │ inline PNG,   │
                     │ explores,     │  │ tiles, filters│  │ SSO embed URL │
                     │ fields,       │  │ 24-col layout │  │               │
                     │ previews      │  │               │  │               │
                     └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
                             │    Looker SDK 4.0 (HTTPS)           │
                             └───────────────┬────────────────────┘
                                     ┌───────▼────────┐
                                     │   Looker API    │
                                     │ (LookML semantic│
                                     │ layer = govern.)│
                                     └────────────────┘
```

### The four agents

| Agent | Runtime | Role | Tools (Looker SDK) |
|---|---|---|---|
| **Orchestrator** | Agent Engine (+ optional Cloud Run for A2A/A2UI) | Understands the request, assembles the `DashboardSpec`, delegates via A2A, asks for confirmations | — (`RemoteA2aAgent` sub-agents only) |
| **Catalog** | Cloud Run (A2A, internal ingress) | Authority over the semantic model: exact `view.field` names, validation, previews | `all_lookml_models`, `lookml_model_explore`, `run_inline_query`, `search_dashboards` |
| **Builder** | Cloud Run (A2A, internal ingress) | **Materializes** the native dashboard | `create_dashboard`, `create_query`, `create_dashboard_element`, `create_dashboard_filter`, layout components |
| **Render/QA** | Cloud Run (A2A, internal ingress) | Visual verification and delivery | `create_dashboard_render_task` (PNG→ADK artifact), `create_sso_embed_url` |

### Design decisions

- **A2A between agents.** Each specialist is an independent A2A server (ADK's `to_a2a()`) with a discoverable AgentCard; the orchestrator consumes them as `RemoteA2aAgent`. You can scale, version, or replace a specialist without touching the rest (even with an agent from another framework that speaks A2A).
- **A2UI toward the user.** The orchestrator advertises the A2UI extension in its AgentCard and emits declarative blueprints (spec wizard, preview, destructive confirmations) as `DataPart application/json+a2ui`. The frontend renders them with native components — never HTML or executable code crossing the trust boundary. See `frontend/README.md`.
- **Two surfaces, one logic.** Gemini Enterprise doesn't render A2UI, so there the experience gracefully degrades to text + inline images (PNGs are stored as **ADK artifacts**, never passing through the model's text) + signed links. The `A2UI_ENABLED` flag controls the contract per surface.
- **The Catalog Agent is the anti-hallucination barrier.** The Builder only uses fields the Catalog validated against LookML (`list_fields` + `preview_query`). Governance keeps living in LookML.
- **Swappable model.** `AGENT_MODEL_PROVIDER` (gemini | claude | claude_native | anthropic) in `agents/common/model_factory.py`, per agent if you want (e.g., Gemini Flash for the catalog, Claude for the orchestrator). For the Claude-on-Vertex routes, enable the model in Model Garden and set `claude_location`.
- **Signed links in a separate tool** (`create_sso_embed_url`): producing the link never blocks the render.

---

## Structure

```
agents/
├── common/            # model_factory (swappable model) + Looker SDK client
├── orchestrator/      # root LlmAgent + RemoteA2aAgent + A2UI contract + entrypoints
│   ├── agent.py             #   A2A sub_agents
│   ├── a2ui_prompt.py       #   A2uiSchemaManager → system prompt with schema/examples
│   ├── agent_engine_app.py  #   Agent Engine entrypoint (AdkApp)
│   └── __main__.py          #   A2A+A2UI server (Cloud Run, custom frontend)
├── catalog_agent/     # semantic discovery (read)
├── builder_agent/     # dashboard creation (write) ← the heart of self-service
├── render_agent/      # inline PNG (artifacts) + SSO embed
└── cloudbuild.yaml    # per-agent build (context shared with common/)

terraform/
├── versions.tf  variables.tf  outputs.tf  terraform.tfvars.example
├── foundation.tf        # APIs, SA + least-privilege IAM, bucket, Secret Manager
├── cloud_run_agents.tf  # Artifact Registry, Cloud Build, 3 internal Cloud Run services
│                        # + public A2A/A2UI surface of the orchestrator
├── agent_engine.tf      # packaging → GCS → Reasoning Engine → GE registration
└── scripts/
    ├── build_source.py        # packages common+orchestrator (tar.gz)
    ├── deploy_agent_engine.py # SDK deploy fallback (agent_engines.create)
    └── register_agent.sh      # Gemini Enterprise registration (Discovery Engine API)

frontend/README.md       # how to connect an A2UI renderer (Lit/Angular/Flutter/CopilotKit)
docs/                    # prerequisites for approval (client/vendor)
```

---

## Prerequisites

- GCP project with billing; Owner role (or equivalent); authenticated `gcloud`; Terraform ≥ 1.7; `python3`.
- A **Looker** instance with API credentials (Client ID/Secret) whose role includes `access_data`, `explore` **and dashboard write permissions** (`create_dashboards` / `manage_dashboards` on the target folder) + a model set with your models.
- **SSO Embed enabled** in Looker (Admin → Embed) for the interactive links.
- A **Gemini Enterprise** app created (you need its `AS_APP` id).
- For Claude routes: model enabled in **Vertex AI Model Garden** (or `ANTHROPIC_API_KEY` for the `anthropic` route).

The full detail, organized by responsible team and with a signature sheet, lives in `docs/prerrequisitos_looker_selfservice_agents.docx`.

## Deployment

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # then fill it in
terraform init
terraform plan
terraform apply
```

Order Terraform resolves: APIs → SA/IAM → bucket → secrets → image builds (Cloud Build) → 3 internal Cloud Run services → orchestrator A2A surface → packaging + Reasoning Engine → GE registration (`register_agent.sh`).

> **Honest caveats:**
> 1. `google_vertex_ai_reasoning_engine` is recent in `google-beta`: verify the nested `spec` names against your provider version. If your version doesn't yet support ADK source packaging, use `scripts/deploy_agent_engine.py` (same end state) and pass the engine id to `register_agent.sh`.
> 2. GE registration is **not idempotent** (no native resource yet): re-applying may duplicate the agent.
> 3. The `requirements.txt` pins are for reference: pin the exact versions you validate in your build so build and runtime match.

## End-to-end test (in Gemini Enterprise)

> "I want an e-commerce sales dashboard: revenue by month, top 10 countries by orders, average ticket as a single value, and a table of orders by status. Global filter by country."

1. The orchestrator delegates to the **Catalog**: resolves `thelook/order_items`, validates `orders.created_month`, `order_items.total_revenue`, etc., and runs a `preview_query`.
2. It proposes the `DashboardSpec` and waits for your confirmation.
3. The **Builder** executes: `create_dashboard` → 4× `add_tile` → `add_dashboard_filter` + `wire_filter_to_tiles` → `apply_grid_layout(2)`.
4. The **Render** shows you the inline PNG and the signed SSO link.
5. You open the dashboard in Looker: it's native, editable, yours.

In the A2UI frontend, steps 1–2 are an **interactive wizard** (explore/field/chart selects) and step 4 a **preview Card** with buttons — same agents, zero duplicated logic.

## Quick troubleshooting

- **"cannot access data"** → almost always the Looker API credentials' role (permission set + model set). `list_models` tells you what it can actually reach.
- **The builder fails creating tiles** → `create_dashboards`/`manage_dashboards` missing from the permission set, or `looker_target_folder_id` isn't writable by the API user.
- **Claude works via direct `stream_query` but GE returns an empty response** → GE↔LiteLlm streaming boundary: try `claude_native`, or `gemini` for the agent facing GE (specialists can stay on Claude).
- **"Environment variable 'GOOGLE_CLOUD_PROJECT' is reserved"** → Agent Engine sets it itself; that's why we use `VERTEXAI_PROJECT`/`VERTEXAI_LOCATION`.
- **A specialist's AgentCard advertises localhost** → check `PUBLIC_URL` in the Cloud Run revision.

## Author

Jose Maldonado
