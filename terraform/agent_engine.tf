# ---------------------------------------------------------------------------
# Empaquetado del código del orquestador (tar.gz -> base64) para Agent Engine
# ---------------------------------------------------------------------------
resource "null_resource" "package_source" {
  triggers = {
    src_hash = sha1(join("", [
      for f in fileset("${path.module}/../agents", "{common,orchestrator}/**") :
      filesha1("${path.module}/../agents/${f}")
    ]))
  }
  provisioner "local-exec" {
    command = "python3 ${path.module}/scripts/build_source.py ${path.module}/../agents ${path.module}/.build"
  }
}

# Subida del paquete de fuente y requirements al bucket de staging
resource "google_storage_bucket_object" "orchestrator_source" {
  name       = "agent-engine/source.tar.gz"
  bucket     = google_storage_bucket.staging.name
  source     = "${path.module}/.build/source.tar.gz"
  depends_on = [null_resource.package_source]
}

resource "google_storage_bucket_object" "orchestrator_requirements" {
  name       = "agent-engine/requirements.txt"
  bucket     = google_storage_bucket.staging.name
  source     = "${path.module}/.build/requirements.txt"
  depends_on = [null_resource.package_source]
}

# ---------------------------------------------------------------------------
# Vertex AI Agent Engine (Reasoning Engine) — despliegue nativo del ADK app.
#
# NOTA IMPORTANTE: google_vertex_ai_reasoning_engine es un recurso reciente en
# google-beta; verifica los nombres anidados de `spec` (package_spec,
# class_methods, deployment_spec) contra los docs de TU versión del provider.
# Si tu versión aún no soporta el empaquetado de fuente ADK, usa el fallback
# scripts/deploy_agent_engine.py (mismo end state) y pásale el engine id a
# scripts/register_agent.sh.
# ---------------------------------------------------------------------------
resource "google_vertex_ai_reasoning_engine" "orchestrator" {
  provider     = google-beta
  region       = var.region
  display_name = "looker-selfservice-orchestrator"
  description  = "Orquestador multi-agente (A2A) de autoservicio de dashboards Looker"

  spec {
    package_spec {
      python_version           = "3.12"
      dependency_files_gcs_uri = "gs://${google_storage_bucket.staging.name}/${google_storage_bucket_object.orchestrator_source.name}"
      requirements_gcs_uri     = "gs://${google_storage_bucket.staging.name}/${google_storage_bucket_object.orchestrator_requirements.name}"
    }
    # Entrypoint del paquete: orchestrator.agent_engine_app:agent_engine
    class_methods {
      name = "stream_query"
    }
    deployment_spec {
      env {
        name  = "AGENT_MODEL_PROVIDER"
        value = var.agent_model_provider
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "CLAUDE_MODEL"
        value = var.claude_model
      }
      env {
        name  = "CLAUDE_LOCATION"
        value = var.claude_location
      }
      env {
        name  = "VERTEXAI_PROJECT"
        value = var.project_id # NO usar GOOGLE_CLOUD_PROJECT: reservado por Agent Engine
      }
      env {
        name  = "VERTEXAI_LOCATION"
        value = var.region
      }
      env {
        name  = "LOOKERSDK_BASE_URL"
        value = var.looker_base_url
      }
      env {
        name  = "LOOKER_MODELS"
        value = var.looker_models
      }
      env {
        name  = "A2UI_ENABLED"
        value = "false" # la superficie GE consume texto+artifacts; A2UI vive en Cloud Run
      }
      env {
        name  = "CATALOG_AGENT_URL"
        value = google_cloud_run_v2_service.specialist["catalog"].uri
      }
      env {
        name  = "BUILDER_AGENT_URL"
        value = google_cloud_run_v2_service.specialist["builder"].uri
      }
      env {
        name  = "RENDER_AGENT_URL"
        value = google_cloud_run_v2_service.specialist["render"].uri
      }
      env {
        name  = "DELIVERABLES_AGENT_URL"
        value = google_cloud_run_v2_service.specialist["deliverables"].uri
      }
      env {
        name = "LOOKERSDK_CLIENT_ID"
        secret_ref {
          secret  = google_secret_manager_secret.looker_client_id.secret_id
          version = "latest"
        }
      }
      env {
        name = "LOOKERSDK_CLIENT_SECRET"
        secret_ref {
          secret  = google_secret_manager_secret.looker_client_secret.secret_id
          version = "latest"
        }
      }
    }
    agent_framework = "google-adk"
  }

  depends_on = [
    data.local_file.packaged_source,
    google_project_iam_member.agents_roles,
    google_cloud_run_v2_service.specialist,
  ]
}

# ---------------------------------------------------------------------------
# Registro del orquestador en Gemini Enterprise (sin recurso nativo aún):
# null_resource + curl a la API de Discovery Engine assistants/agents.
# ATENCIÓN: NO es idempotente; re-aplicar puede duplicar el agente en GE.
# ---------------------------------------------------------------------------
resource "null_resource" "register_in_ge" {
  triggers = {
    engine = google_vertex_ai_reasoning_engine.orchestrator.id
  }
  provisioner "local-exec" {
    command = <<-EOT
      bash ${path.module}/scripts/register_agent.sh \
        "${var.project_id}" \
        "${var.ge_location}" \
        "${var.ge_app_id}" \
        "${google_vertex_ai_reasoning_engine.orchestrator.id}" \
        "Looker Self-Service" \
        "Crea dashboards nativos de Looker a partir de lenguaje natural"
    EOT
  }
}
