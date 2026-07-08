# ---------------------------------------------------------------------------
# Registro de imágenes + build + Cloud Run por agente especialista (A2A)
# ---------------------------------------------------------------------------
resource "google_artifact_registry_repository" "agents" {
  location      = var.region
  repository_id = "looker-agents"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

locals {
  registry = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.agents.repository_id}"

  specialist_agents = {
    catalog = "catalog_agent"
    builder = "builder_agent"
    render  = "render_agent"
    excel   = "excel_agent"
  }

  # Env vars comunes a todos los agentes
  common_env = {
    AGENT_MODEL_PROVIDER = var.agent_model_provider
    GEMINI_MODEL         = var.gemini_model
    CLAUDE_MODEL         = var.claude_model
    CLAUDE_LOCATION      = var.claude_location
    VERTEXAI_PROJECT     = var.project_id
    VERTEXAI_LOCATION    = var.region
    LOOKERSDK_BASE_URL   = var.looker_base_url
    LOOKER_MODELS        = var.looker_models
    LOOKER_TARGET_FOLDER_ID = var.looker_target_folder_id
    GOOGLE_GENAI_USE_VERTEXAI = "TRUE"
    EXPORT_BUCKET             = google_storage_bucket.staging.name
    TEMPLATES_BUCKET          = google_storage_bucket.staging.name
    TEMPLATES_PREFIX          = "templates"
  }
}

# Build de la imagen de cada agente (Cloud Build; contexto = ../agents)
resource "null_resource" "build_image" {
  for_each = merge(local.specialist_agents,
    var.deploy_orchestrator_a2a_surface ? { orchestrator = "orchestrator" } : {})

  triggers = {
    src_hash = sha1(join("", [
      for f in fileset("${path.module}/../agents", "{common,${each.value}}/**") :
      filesha1("${path.module}/../agents/${f}")
    ]))
  }

  provisioner "local-exec" {
    working_dir = "${path.module}/../agents"
    command     = <<-EOT
      gcloud builds submit . \
        --project=${var.project_id} \
        --config=cloudbuild.yaml \
        --gcs-source-staging-dir=gs://${google_storage_bucket.staging.name}/cloudbuild \
        --substitutions=_AGENT=${each.value},_REGISTRY=${local.registry} \
        --quiet
    EOT
  }
  depends_on = [google_artifact_registry_repository.agents]
}

resource "google_cloud_run_v2_service" "specialist" {
  for_each = local.specialist_agents

  name                = "looker-${each.key}-agent"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_INTERNAL_ONLY" # solo el orquestador les habla

  template {
    service_account = google_service_account.agents.email
    containers {
      image = "${local.registry}/${each.value}:latest"
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      dynamic "env" {
        for_each = local.common_env
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "LOOKERSDK_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.looker_client_id.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "LOOKERSDK_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.looker_client_secret.secret_id
            version = "latest"
          }
        }
      }
      env {
        # URL determinística de Cloud Run: el AgentCard debe anunciarla.
        name  = "PUBLIC_URL"
        value = "https://looker-${each.key}-agent-${var.project_number}.${var.region}.run.app"
      }
    }
    scaling {
      max_instance_count = 3
    }
  }
  depends_on = [null_resource.build_image]
}

# El orquestador (SA de agentes) puede invocar a los especialistas
resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = google_cloud_run_v2_service.specialist
  name     = each.value.name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.agents.email}"
}

# ---------------------------------------------------------------------------
# Superficie A2A + A2UI del orquestador (para el frontend propio)
# ---------------------------------------------------------------------------
resource "google_cloud_run_v2_service" "orchestrator_a2a" {
  count               = var.deploy_orchestrator_a2a_surface ? 1 : 0
  name                = "looker-orchestrator-a2a"
  location            = var.region
  deletion_protection = false
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.agents.email
    containers {
      image = "${local.registry}/orchestrator:latest"
      resources {
        limits = { cpu = "2", memory = "2Gi" }
      }
      dynamic "env" {
        for_each = merge(local.common_env, {
          A2UI_ENABLED      = tostring(var.a2ui_enabled)
          CATALOG_AGENT_URL = google_cloud_run_v2_service.specialist["catalog"].uri
          BUILDER_AGENT_URL = google_cloud_run_v2_service.specialist["builder"].uri
          RENDER_AGENT_URL  = google_cloud_run_v2_service.specialist["render"].uri
          EXCEL_AGENT_URL   = google_cloud_run_v2_service.specialist["excel"].uri
        })
        content {
          name  = env.key
          value = env.value
        }
      }
      env {
        name = "LOOKERSDK_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.looker_client_id.secret_id
            version = "latest"
          }
        }
      }
      env {
        name = "LOOKERSDK_CLIENT_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.looker_client_secret.secret_id
            version = "latest"
          }
        }
      }
    }
  }
  depends_on = [null_resource.build_image, google_cloud_run_v2_service.specialist]
}
