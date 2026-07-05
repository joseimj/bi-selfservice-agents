# ---------------------------------------------------------------------------
# APIs
# ---------------------------------------------------------------------------
locals {
  services = [
    "aiplatform.googleapis.com",
    "discoveryengine.googleapis.com",
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com",
    "secretmanager.googleapis.com",
    "iam.googleapis.com",
    "storage.googleapis.com",
    "cloudresourcemanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Service account de los agentes (mínimo privilegio)
# ---------------------------------------------------------------------------
resource "google_service_account" "agents" {
  account_id   = "looker-selfservice-agents"
  display_name = "Looker Self-Service Agents (ADK/A2A)"
  depends_on   = [google_project_service.apis]
}

resource "google_project_iam_member" "agents_roles" {
  for_each = toset([
    "roles/aiplatform.user",          # invocar modelos Vertex (Gemini/Claude)
    "roles/storage.objectAdmin",      # staging + artifacts en el bucket
    "roles/logging.logWriter",
    "roles/secretmanager.secretAccessor",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.agents.email}"
}

# El service agent de Reasoning Engine necesita leer el paquete de staging
resource "google_project_iam_member" "reasoning_engine_sa" {
  project = var.project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:service-${var.project_number}@gcp-sa-aiplatform-re.iam.gserviceaccount.com"
  depends_on = [google_project_service.apis]
}

# ---------------------------------------------------------------------------
# Bucket de staging / artifacts
# ---------------------------------------------------------------------------
resource "google_storage_bucket" "staging" {
  name                        = var.staging_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = true
}

# ---------------------------------------------------------------------------
# Secretos de Looker
# ---------------------------------------------------------------------------
resource "google_secret_manager_secret" "looker_client_id" {
  secret_id = "looker-client-id"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "looker_client_id" {
  secret      = google_secret_manager_secret.looker_client_id.id
  secret_data = var.looker_client_id
}

resource "google_secret_manager_secret" "looker_client_secret" {
  secret_id = "looker-client-secret"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "looker_client_secret" {
  secret      = google_secret_manager_secret.looker_client_secret.id
  secret_data = var.looker_client_secret
}
