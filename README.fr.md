# bi-selfservice-agents

[Español](README.md) | [English](README.en.md) | **Français** | [Português](README.pt.md)

**Le self-service analytique au niveau supérieur : un système multi-agents (ADK + A2A + A2UI) qui CRÉE des dashboards natifs dans Looker à partir du langage naturel, déployable de bout en bout avec Terraform sur GCP et enregistré dans Gemini Enterprise.**

Le saut par rapport au schéma habituel de « l'agent qui affiche des images » : ici, le résultat de chaque conversation est un vrai dashboard user-defined dans Looker (tuiles avec requêtes, filtres cross-tile, mise en page), éditable et gouverné par LookML.

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

### Les quatre agents

| Agent | Runtime | Rôle | Tools (Looker SDK) |
|---|---|---|---|
| **Orchestrator** | Agent Engine (+ Cloud Run optionnel pour A2A/A2UI) | Comprend la demande, assemble le `DashboardSpec`, délègue via A2A, demande les confirmations | — (sous-agents `RemoteA2aAgent` uniquement) |
| **Catalog** | Cloud Run (A2A, ingress interne) | Autorité du modèle sémantique : noms exacts `view.field`, validation, aperçus | `all_lookml_models`, `lookml_model_explore`, `run_inline_query`, `search_dashboards` |
| **Builder** | Cloud Run (A2A, ingress interne) | **Matérialise** le dashboard natif | `create_dashboard`, `create_query`, `create_dashboard_element`, `create_dashboard_filter`, layout components |
| **Render/QA** | Cloud Run (A2A, ingress interne) | Vérification visuelle et livraison | `create_dashboard_render_task` (PNG→artifact ADK), `create_sso_embed_url` |

### Décisions de conception

- **A2A entre agents.** Chaque spécialiste est un serveur A2A indépendant (`to_a2a()` de l'ADK) avec une AgentCard découvrable ; l'orchestrateur les consomme en tant que `RemoteA2aAgent`. Vous pouvez mettre à l'échelle, versionner ou remplacer un spécialiste sans toucher au reste (même par un agent d'un autre framework qui parle A2A).
- **A2UI vers l'utilisateur.** L'orchestrateur annonce l'extension A2UI dans son AgentCard et émet des blueprints déclaratifs (wizard de spec, aperçu, confirmations destructives) sous forme de `DataPart application/json+a2ui`. Le frontend les affiche avec des composants natifs — jamais de HTML ni de code exécutable traversant la frontière de confiance. Voir `frontend/README.md`.
- **Deux surfaces, une seule logique.** Gemini Enterprise n'affiche pas l'A2UI : l'expérience s'y dégrade donc élégamment en texte + images inline (les PNG sont stockés comme **artifacts ADK**, sans jamais passer par le texte du modèle) + liens signés. Le flag `A2UI_ENABLED` contrôle le contrat par surface.
- **Le Catalog Agent est la barrière anti-hallucination.** Le Builder n'utilise que des champs validés par le Catalog contre LookML (`list_fields` + `preview_query`). La gouvernance continue de vivre dans LookML.
- **Modèle interchangeable.** `AGENT_MODEL_PROVIDER` (gemini | claude | claude_native | anthropic) dans `agents/common/model_factory.py`, par agent si vous le souhaitez (p. ex. Gemini Flash pour le catalogue, Claude pour l'orchestrateur). Pour les routes Claude-sur-Vertex, activez le modèle dans Model Garden et définissez `claude_location`.
- **Liens signés dans un tool séparé** (`create_sso_embed_url`) : produire le lien ne bloque jamais le rendu.

---

## Structure

```
agents/
├── common/            # model_factory (modèle interchangeable) + client Looker SDK
├── orchestrator/      # LlmAgent racine + RemoteA2aAgent + contrat A2UI + entrypoints
│   ├── agent.py             #   sous-agents A2A
│   ├── a2ui_prompt.py       #   A2uiSchemaManager → system prompt avec schéma/exemples
│   ├── agent_engine_app.py  #   entrypoint Agent Engine (AdkApp)
│   └── __main__.py          #   serveur A2A+A2UI (Cloud Run, frontend dédié)
├── catalog_agent/     # découverte sémantique (lecture)
├── builder_agent/     # création de dashboards (écriture) ← le cœur du self-service
├── render_agent/      # PNG inline (artifacts) + SSO embed
└── cloudbuild.yaml    # build par agent (contexte partagé avec common/)

terraform/
├── versions.tf  variables.tf  outputs.tf  terraform.tfvars.example
├── foundation.tf        # APIs, SA + IAM moindre privilège, bucket, Secret Manager
├── cloud_run_agents.tf  # Artifact Registry, Cloud Build, 3 services Cloud Run internes
│                        # + surface A2A/A2UI publique de l'orchestrateur
├── agent_engine.tf      # packaging → GCS → Reasoning Engine → enregistrement GE
└── scripts/
    ├── build_source.py        # empaquette common+orchestrator (tar.gz)
    ├── deploy_agent_engine.py # déploiement de secours via SDK (agent_engines.create)
    └── register_agent.sh      # enregistrement dans Gemini Enterprise (Discovery Engine API)

frontend/README.md       # comment connecter un renderer A2UI (Lit/Angular/Flutter/CopilotKit)
docs/                    # prérequis pour approbation (client/fournisseur)
```

---

## Prérequis

- Projet GCP avec facturation ; rôle Owner (ou équivalent) ; `gcloud` authentifié ; Terraform ≥ 1.7 ; `python3`.
- Une instance **Looker** avec des identifiants API (Client ID/Secret) dont le rôle inclut `access_data`, `explore` **et les permissions d'écriture de dashboards** (`create_dashboards` / `manage_dashboards` sur le dossier cible) + un model set avec vos modèles.
- **SSO Embed activé** dans Looker (Admin → Embed) pour les liens interactifs.
- Une app **Gemini Enterprise** créée (il vous faut son id `AS_APP`).
- Pour les routes Claude : modèle activé dans **Vertex AI Model Garden** (ou `ANTHROPIC_API_KEY` pour la route `anthropic`).

Le détail complet, organisé par équipe responsable et avec une feuille de signatures, se trouve dans `docs/prerrequisitos_looker_selfservice_agents.docx`.

## Déploiement

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars   # puis remplissez-le
terraform init
terraform plan
terraform apply
```

Ordre résolu par Terraform : APIs → SA/IAM → bucket → secrets → build des images (Cloud Build) → 3 Cloud Run internes → surface A2A de l'orchestrateur → packaging + Reasoning Engine → enregistrement GE (`register_agent.sh`).

> **Avertissements honnêtes :**
> 1. `google_vertex_ai_reasoning_engine` est récent dans `google-beta` : vérifiez les noms imbriqués de `spec` contre la version de votre provider. Si votre version ne prend pas encore en charge l'empaquetage de source ADK, utilisez `scripts/deploy_agent_engine.py` (même état final) et passez l'engine id à `register_agent.sh`.
> 2. L'enregistrement dans GE **n'est pas idempotent** (pas encore de ressource native) : ré-appliquer peut dupliquer l'agent.
> 3. Les versions épinglées de `requirements.txt` sont indicatives : figez les versions exactes validées dans votre build pour que build et runtime coïncident.

## Test de bout en bout (dans Gemini Enterprise)

> « Je veux un tableau de bord des ventes e-commerce : chiffre d'affaires par mois, top 10 des pays par commandes, panier moyen en single value et un tableau des commandes par statut. Filtre global par pays. »

1. L'orchestrateur délègue au **Catalog** : il résout `thelook/order_items`, valide `orders.created_month`, `order_items.total_revenue`, etc., et exécute un `preview_query`.
2. Il vous propose le `DashboardSpec` et attend votre confirmation.
3. Le **Builder** exécute : `create_dashboard` → 4× `add_tile` → `add_dashboard_filter` + `wire_filter_to_tiles` → `apply_grid_layout(2)`.
4. Le **Render** vous montre le PNG inline et le lien SSO signé.
5. Vous ouvrez le dashboard dans Looker : il est natif, éditable, à vous.

Dans le frontend A2UI, les étapes 1–2 sont un **wizard interactif** (sélecteurs d'explore/champs/graphiques) et l'étape 4 une **Card d'aperçu** avec boutons — mêmes agents, zéro logique dupliquée.

## Dépannage rapide

- **« cannot access data »** → presque toujours le rôle des identifiants API dans Looker (permission set + model set). `list_models` vous dit ce qui est réellement accessible.
- **Le builder échoue à créer des tuiles** → `create_dashboards`/`manage_dashboards` manquent dans le permission set, ou le `looker_target_folder_id` n'est pas accessible en écriture pour l'utilisateur API.
- **Claude fonctionne en `stream_query` direct mais GE renvoie une réponse vide** → frontière de streaming GE↔LiteLlm : essayez `claude_native`, ou `gemini` pour l'agent exposé à GE (les spécialistes peuvent rester sur Claude).
- **« Environment variable 'GOOGLE_CLOUD_PROJECT' is reserved »** → Agent Engine la définit lui-même ; c'est pourquoi nous utilisons `VERTEXAI_PROJECT`/`VERTEXAI_LOCATION`.
- **L'AgentCard d'un spécialiste annonce localhost** → vérifiez `PUBLIC_URL` dans la révision Cloud Run.

## Auteur

Jose Maldonado
