# bi-selfservice-agents

[Español](README.md) | [English](README.en.md) | [Français](README.fr.md) | **Português**

**Autoatendimento analítico de próximo nível: um sistema multiagente (ADK + A2A + A2UI) que CRIA dashboards nativos no Looker a partir de linguagem natural, implantável de ponta a ponta com Terraform no GCP e registrado no Gemini Enterprise.**

O salto em relação ao padrão habitual de «agente que renderiza imagens»: aqui, o resultado de cada conversa é um dashboard user-defined real no Looker (tiles com queries, filtros cross-tile, layout), editável e governado pelo LookML.

---

## Arquitetura

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

### Os quatro agentes

| Agente | Runtime | Papel | Tools (Looker SDK) |
|---|---|---|---|
| **Orchestrator** | Agent Engine (+ Cloud Run opcional para A2A/A2UI) | Entende o pedido, monta o `DashboardSpec`, delega via A2A, pede confirmações | — (apenas sub-agentes `RemoteA2aAgent`) |
| **Catalog** | Cloud Run (A2A, ingress interno) | Autoridade do modelo semântico: nomes exatos `view.field`, validação, previews | `all_lookml_models`, `lookml_model_explore`, `run_inline_query`, `search_dashboards` |
| **Builder** | Cloud Run (A2A, ingress interno) | **Materializa** o dashboard nativo | `create_dashboard`, `create_query`, `create_dashboard_element`, `create_dashboard_filter`, layout components |
| **Render/QA** | Cloud Run (A2A, ingress interno) | Verificação visual e entrega | `create_dashboard_render_task` (PNG→artifact ADK), `create_sso_embed_url` |

### Decisões de design

- **A2A entre agentes.** Cada especialista é um servidor A2A independente (`to_a2a()` do ADK) com AgentCard descobrível; o orquestrador os consome como `RemoteA2aAgent`. É possível escalar, versionar ou substituir um especialista sem tocar no resto (inclusive por um agente de outro framework que fale A2A).
- **A2UI em direção ao usuário.** O orquestrador anuncia a extensão A2UI no seu AgentCard e emite blueprints declarativos (wizard de spec, preview, confirmações destrutivas) como `DataPart application/json+a2ui`. O frontend os renderiza com componentes nativos — nunca HTML nem código executável cruzando o trust boundary. Ver `frontend/README.md`.
- **Duas superfícies, uma lógica.** O Gemini Enterprise não renderiza A2UI, então ali a experiência degrada com elegância para texto + imagens inline (os PNG são salvos como **artifacts ADK**, nunca passam pelo texto do modelo) + links assinados. A flag `A2UI_ENABLED` controla o contrato por superfície.
- **O Catalog Agent é a barreira anti-alucinação.** O Builder só usa campos que o Catalog validou contra o LookML (`list_fields` + `preview_query`). A governança continua vivendo no LookML.
- **Modelo intercambiável.** `AGENT_MODEL_PROVIDER` (gemini | claude | claude_native | anthropic) em `agents/common/model_factory.py`, por agente se quiser (p. ex. Gemini Flash para o catálogo, Claude para o orquestrador). Para as rotas Claude-no-Vertex, habilite o modelo no Model Garden e defina `claude_location`.
- **Links assinados em tool separada** (`create_sso_embed_url`): produzir o link nunca bloqueia o render.

---

## Estrutura

```
agents/
├── common/            # model_factory (modelo intercambiável) + cliente Looker SDK
├── orchestrator/      # LlmAgent raiz + RemoteA2aAgent + contrato A2UI + entrypoints
│   ├── agent.py             #   sub_agents A2A
│   ├── a2ui_prompt.py       #   A2uiSchemaManager → system prompt com schema/exemplos
│   ├── agent_engine_app.py  #   entrypoint do Agent Engine (AdkApp)
│   └── __main__.py          #   servidor A2A+A2UI (Cloud Run, frontend próprio)
├── catalog_agent/     # descoberta semântica (leitura)
├── builder_agent/     # criação de dashboards (escrita) ← o coração do autoatendimento
├── render_agent/      # PNG inline (artifacts) + SSO embed
└── cloudbuild.yaml    # build por agente (contexto compartilhado com common/)

terraform/
├── versions.tf  variables.tf  outputs.tf  terraform.tfvars.example
├── foundation.tf        # APIs, SA + IAM de mínimo privilégio, bucket, Secret Manager
├── cloud_run_agents.tf  # Artifact Registry, Cloud Build, 3 Cloud Run internos
│                        # + superfície A2A/A2UI pública do orquestrador
├── agent_engine.tf      # empacotamento → GCS → Reasoning Engine → registro no GE
└── scripts/
    ├── build_source.py        # empacota common+orchestrator (tar.gz)
    ├── deploy_agent_engine.py # fallback de deploy via SDK (agent_engines.create)
    └── register_agent.sh      # registro no Gemini Enterprise (Discovery Engine API)

frontend/README.md       # como conectar um renderer A2UI (Lit/Angular/Flutter/CopilotKit)
docs/                    # pré-requisitos para aprovação (cliente/fornecedor)
```

---

## Pré-requisitos

- Projeto GCP com billing; papel Owner (ou equivalente); `gcloud` autenticado; Terraform ≥ 1.7; `python3`.
- Instância do **Looker** com credenciais de API (Client ID/Secret) cujo papel inclua `access_data`, `explore` **e permissões de escrita de dashboards** (`create_dashboards` / `manage_dashboards` sobre a pasta de destino) + um model set com seus modelos.
- **Embed SSO habilitado** no Looker (Admin → Embed) para os links interativos.
- Um app do **Gemini Enterprise** criado (você precisa do id `AS_APP`).
- Para rotas Claude: modelo habilitado no **Vertex AI Model Garden** (ou `ANTHROPIC_API_KEY` para a rota `anthropic`).

O detalhamento completo, organizado por equipe responsável e com folha de assinaturas, está em `docs/prerrequisitos_looker_selfservice_agents.docx`.

## Implantação

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # e preencha
terraform init
terraform plan
terraform apply
```

Ordem resolvida pelo Terraform: APIs → SA/IAM → bucket → secrets → build das imagens (Cloud Build) → 3 Cloud Run internos → superfície A2A do orquestrador → empacotamento + Reasoning Engine → registro no GE (`register_agent.sh`).

> **Avisos honestos:**
> 1. `google_vertex_ai_reasoning_engine` é recente no `google-beta`: verifique os nomes aninhados de `spec` contra a versão do seu provider. Se a sua versão ainda não suporta o empacotamento de fonte ADK, use `scripts/deploy_agent_engine.py` (mesmo estado final) e passe o engine id para `register_agent.sh`.
> 2. O registro no GE **não é idempotente** (ainda não há recurso nativo): reaplicar pode duplicar o agente.
> 3. Os pins do `requirements.txt` são de referência: fixe as versões exatas validadas no seu build para que build e runtime coincidam.

## Teste de ponta a ponta (no Gemini Enterprise)

> «Quero um painel de vendas de e-commerce: receita por mês, top 10 países por pedidos, ticket médio como single value e uma tabela de pedidos por status. Filtro global por país.»

1. O orquestrador delega ao **Catalog**: resolve `thelook/order_items`, valida `orders.created_month`, `order_items.total_revenue`, etc., e executa um `preview_query`.
2. Ele propõe o `DashboardSpec` e aguarda a sua confirmação.
3. O **Builder** executa: `create_dashboard` → 4× `add_tile` → `add_dashboard_filter` + `wire_filter_to_tiles` → `apply_grid_layout(2)`.
4. O **Render** mostra o PNG inline e o link SSO assinado.
5. Você abre o dashboard no Looker: é nativo, editável, seu.

No frontend A2UI, os passos 1–2 são um **wizard interativo** (selects de explore/campos/gráficos) e o passo 4 um **Card de preview** com botões — mesmos agentes, zero lógica duplicada.

## Solução rápida de problemas

- **"cannot access data"** → quase sempre é o papel das credenciais de API no Looker (permission set + model set). `list_models` mostra o que realmente está acessível.
- **O builder falha ao criar tiles** → falta `create_dashboards`/`manage_dashboards` no permission set, ou o `looker_target_folder_id` não é gravável pelo usuário de API.
- **Claude funciona em `stream_query` direto mas o GE devolve resposta vazia** → fronteira de streaming GE↔LiteLlm: tente `claude_native`, ou `gemini` para o agente exposto ao GE (os especialistas podem continuar no Claude).
- **"Environment variable 'GOOGLE_CLOUD_PROJECT' is reserved"** → o Agent Engine a define sozinho; por isso usamos `VERTEXAI_PROJECT`/`VERTEXAI_LOCATION`.
- **O AgentCard de um especialista anuncia localhost** → verifique `PUBLIC_URL` na revisão do Cloud Run.

## Autor

Jose Maldonado
