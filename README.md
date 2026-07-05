# looker-selfservice-agents

**Autoservicio analítico de siguiente nivel: un sistema multi-agente (ADK + A2A + A2UI) que CREA dashboards nativos en Looker desde lenguaje natural, desplegable end-to-end con Terraform en GCP y registrado en Gemini Enterprise.**

Inspirado en [hendrixtlan/gemini_looker](https://github.com/hendrixtlan/gemini_looker), pero da el salto de *renderizar* dashboards a *construirlos*: el resultado de cada conversación es un dashboard user-defined real en Looker (tiles con queries, filtros cross-tile, layout), editable y gobernado por LookML.

---

## Arquitectura

```
                         ┌────────────────────────────┐
   Superficie 1          │      Gemini Enterprise      │  texto + imágenes inline
   (empleados)           └──────────────┬─────────────┘  (artifacts) + links SSO
                                        │
                          ┌─────────────▼──────────────┐
                          │  Vertex AI Agent Engine     │
                          │  ORQUESTADOR (ADK LlmAgent) │  modelo intercambiable:
                          │  looker_selfservice_        │  gemini | claude |
                          │  orchestrator               │  claude_native | anthropic
                          └───────┬──────────┬─────────┘
   Superficie 2                   │   A2A    │   A2A (AgentCards en
   (frontend propio)              │ (JSON-RPC│    /.well-known/agent-card.json)
 ┌──────────────────┐             │  /HTTP)  │
 │ Frontend A2UI    │   A2A +     │          │
 │ (Lit/Angular/    │◄──A2UI──────┤          │
 │  Flutter)        │  DataPart   │          │
 └──────────────────┘  json+a2ui  │          │
                     ┌────────────▼──┐  ┌────▼──────────┐  ┌───────────────┐
                     │ CATALOG AGENT │  │ BUILDER AGENT │  │ RENDER AGENT  │
                     │ (Cloud Run)   │  │ (Cloud Run)   │  │ (Cloud Run)   │
                     │ modelos,      │  │ create_dash,  │  │ PNG inline,   │
                     │ explores,     │  │ tiles, filtros│  │ SSO embed URL │
                     │ campos,       │  │ layout 24-col │  │               │
                     │ previews      │  │               │  │               │
                     └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
                             │    Looker SDK 4.0 (HTTPS)           │
                             └───────────────┬────────────────────┘
                                     ┌───────▼────────┐
                                     │   Looker API    │
                                     │ (capa semántica │
                                     │  LookML = gob.) │
                                     └────────────────┘
```

### Los cuatro agentes

| Agente | Runtime | Rol | Tools (Looker SDK) |
|---|---|---|---|
| **Orchestrator** | Agent Engine (+ Cloud Run opcional para A2A/A2UI) | Entiende la petición, arma el `DashboardSpec`, delega vía A2A, pide confirmaciones | — (solo `RemoteA2aAgent` sub-agents) |
| **Catalog** | Cloud Run (A2A, ingress interno) | Autoridad del modelo semántico: nombres exactos `view.field`, validación, previews | `all_lookml_models`, `lookml_model_explore`, `run_inline_query`, `search_dashboards` |
| **Builder** | Cloud Run (A2A, ingress interno) | **Materializa** el dashboard nativo | `create_dashboard`, `create_query`, `create_dashboard_element`, `create_dashboard_filter`, layout components |
| **Render/QA** | Cloud Run (A2A, ingress interno) | Verificación visual y entrega | `create_dashboard_render_task` (PNG→artifact ADK), `create_sso_embed_url` |

### Decisiones de diseño

- **A2A entre agentes.** Cada especialista es un servidor A2A independiente (`to_a2a()` del ADK) con su AgentCard descubrible; el orquestador los consume como `RemoteA2aAgent`. Puedes escalar, versionar o reemplazar un especialista sin tocar el resto (incluso por un agente de otro framework que hable A2A).
- **A2UI hacia el usuario.** El orquestador anuncia la extensión A2UI en su AgentCard y emite blueprints declarativos (wizard de spec, preview, confirmaciones destructivas) como `DataPart application/json+a2ui`. El frontend los renderiza con componentes nativos — nunca HTML ni código ejecutable cruzando el trust boundary. Ver `frontend/README.md`.
- **Dos superficies, una lógica.** Gemini Enterprise no renderiza A2UI, así que ahí la experiencia degrada con gracia a texto + imágenes inline (los PNG se guardan como **artifacts ADK**, nunca pasan por el texto del modelo) + links firmados. El flag `A2UI_ENABLED` controla el contrato por superficie.
- **El Catalog Agent es la barrera anti-alucinación.** El Builder solo usa campos que el Catalog validó contra LookML (`list_fields` + `preview_query`). La gobernanza sigue viviendo en LookML.
- **Modelo intercambiable.** `AGENT_MODEL_PROVIDER` (gemini | claude | claude_native | anthropic) en `agents/common/model_factory.py`, por agente si quieres (p.ej. Gemini Flash para catálogo, Claude para el orquestador). Para las rutas Claude-en-Vertex, habilita el modelo en Model Garden y fija `claude_location`.
- **Links firmados en tool separada** (`create_sso_embed_url`): producir el link nunca bloquea el render.

---

## Estructura

```
agents/
├── common/            # model_factory (modelo intercambiable) + cliente Looker SDK
├── orchestrator/      # LlmAgent raíz + RemoteA2aAgent + contrato A2UI + entrypoints
│   ├── agent.py             #   sub_agents A2A
│   ├── a2ui_prompt.py       #   A2uiSchemaManager → system prompt con schema/examples
│   ├── agent_engine_app.py  #   entrypoint Agent Engine (AdkApp)
│   └── __main__.py          #   servidor A2A+A2UI (Cloud Run, frontend propio)
├── catalog_agent/     # descubrimiento semántico (read)
├── builder_agent/     # creación de dashboards (write) ← el corazón del autoservicio
├── render_agent/      # PNG inline (artifacts) + SSO embed
└── cloudbuild.yaml    # build por agente (contexto compartido con common/)

terraform/
├── versions.tf  variables.tf  outputs.tf  terraform.tfvars.example
├── foundation.tf        # APIs, SA + IAM mínimo, bucket, Secret Manager
├── cloud_run_agents.tf  # Artifact Registry, Cloud Build, 3 Cloud Run internos
│                        # + superficie A2A/A2UI pública del orquestador
├── agent_engine.tf      # empaquetado → GCS → Reasoning Engine → registro en GE
└── scripts/
    ├── build_source.py        # empaqueta common+orchestrator (tar.gz)
    ├── deploy_agent_engine.py # fallback de deploy vía SDK (agent_engines.create)
    └── register_agent.sh      # registro en Gemini Enterprise (Discovery Engine API)

frontend/README.md       # cómo conectar un renderer A2UI (Lit/Angular/Flutter/CopilotKit)
```

---

## Prerrequisitos

- Proyecto GCP con billing; rol Owner (o equivalente); `gcloud` autenticado; Terraform ≥ 1.7; `python3`.
- Instancia de **Looker** con credenciales API (Client ID/Secret) cuyo rol incluya `access_data`, `explore` **y permisos de escritura de dashboards** (`create_dashboards` / `manage_dashboards` sobre el folder destino) + un model set con tus modelos.
- **Embed SSO habilitado** en Looker (Admin → Embed) para los links interactivos.
- Una app de **Gemini Enterprise** creada (necesitas su `AS_APP` id).
- Para rutas Claude: modelo habilitado en **Vertex AI Model Garden** (o `ANTHROPIC_API_KEY` para la ruta `anthropic`).

## Despliegue

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # y rellénalo
terraform init
terraform plan
terraform apply
```

Orden que resuelve Terraform: APIs → SA/IAM → bucket → secretos → build de imágenes (Cloud Build) → 3 Cloud Run internos → superficie A2A del orquestador → empaquetado + Reasoning Engine → registro en GE (`register_agent.sh`).

> **Avisos honestos (los mismos que el repo de referencia, y aplican aquí):**
> 1. `google_vertex_ai_reasoning_engine` es reciente en `google-beta`: verifica los nombres anidados de `spec` contra la versión de tu provider. Si tu versión aún no soporta el empaquetado de fuente ADK, usa `scripts/deploy_agent_engine.py` (mismo end state) y pasa el engine id a `register_agent.sh`.
> 2. El registro en GE **no es idempotente** (no hay recurso nativo aún): re-aplicar puede duplicar el agente.
> 3. Los pins de `requirements.txt` son de referencia: fija las versiones exactas que valides en tu build para que build y runtime coincidan.

## Prueba end-to-end (en Gemini Enterprise)

> «Quiero un tablero de ventas de e-commerce: ingresos por mes, top 10 países por órdenes, ticket promedio como single value y una tabla de órdenes por estado. Filtro global por país.»

1. El orquestador delega al **Catalog**: resuelve `thelook/order_items`, valida `orders.created_month`, `order_items.total_revenue`, etc., y hace un `preview_query`.
2. Te propone el `DashboardSpec` y espera tu confirmación.
3. El **Builder** ejecuta: `create_dashboard` → 4× `add_tile` → `add_dashboard_filter` + `wire_filter_to_tiles` → `apply_grid_layout(2)`.
4. El **Render** te muestra el PNG inline y el link SSO firmado.
5. Abres el dashboard en Looker: es nativo, editable, tuyo.

En el frontend A2UI, los pasos 1–2 son un **wizard interactivo** (selects de explore/campos/gráficos) y el paso 4 un **Card de preview** con botones — mismos agentes, cero lógica duplicada.

## Troubleshooting rápido

- **"cannot access data"** → casi siempre es el rol de las credenciales API en Looker (permission set + model set). `list_models` te dice qué alcanza realmente.
- **El builder falla creando tiles** → falta `create_dashboards`/`manage_dashboards` en el permission set, o el `looker_target_folder_id` no es escribible por el usuario API.
- **Claude funciona en `stream_query` directo pero GE devuelve respuesta vacía** → frontera de streaming GE↔LiteLlm: prueba `claude_native`, o `gemini` para el agente que da la cara a GE (los especialistas pueden seguir en Claude).
- **"Environment variable 'GOOGLE_CLOUD_PROJECT' is reserved"** → Agent Engine la setea él mismo; por eso usamos `VERTEXAI_PROJECT`/`VERTEXAI_LOCATION`.
- **El AgentCard de un especialista anuncia localhost** → revisa `PUBLIC_URL` en la revisión de Cloud Run.

## Licencia

MIT.
