variable "project_id" {
  description = "Proyecto GCP"
  type        = string
}

variable "project_number" {
  description = "Número del proyecto GCP"
  type        = string
}

variable "region" {
  description = "Región para Cloud Run / Agent Engine"
  type        = string
  default     = "us-central1"
}

variable "staging_bucket_name" {
  description = "Bucket GCS para staging del deploy de Agent Engine y artifacts"
  type        = string
}

# ---------- Looker ----------
variable "looker_base_url" {
  description = "URL de la API de Looker, p.ej. https://miorg.looker.com"
  type        = string
}

variable "looker_client_id" {
  description = "Client ID de la API de Looker"
  type        = string
  sensitive   = true
}

variable "looker_client_secret" {
  description = "Client Secret de la API de Looker"
  type        = string
  sensitive   = true
}

variable "looker_models" {
  description = "Modelos LookML permitidos, JSON string, p.ej. [\"thelook\"]"
  type        = string
  default     = "[\"thelook\"]"
}

variable "looker_target_folder_id" {
  description = "Folder de Looker donde el builder crea los dashboards (vacío = personal del usuario API)"
  type        = string
  default     = ""
}

# ---------- Gemini Enterprise ----------
variable "ge_app_id" {
  description = "ID de la app de Gemini Enterprise (AS_APP) donde se registra el orquestador"
  type        = string
}

variable "ge_location" {
  description = "Location del engine de Gemini Enterprise (global | us | eu)"
  type        = string
  default     = "us"
}

# ---------- Modelo intercambiable ----------
variable "agent_model_provider" {
  description = "gemini | claude | claude_native | anthropic"
  type        = string
  default     = "gemini"
  validation {
    condition     = contains(["gemini", "claude", "claude_native", "anthropic"], var.agent_model_provider)
    error_message = "agent_model_provider debe ser gemini, claude, claude_native o anthropic."
  }
}

variable "gemini_model" {
  type    = string
  default = "gemini-2.5-flash"
}

variable "claude_model" {
  type    = string
  default = "claude-sonnet-4-6"
}

variable "claude_location" {
  description = "Región de Vertex que sirve Claude (rutas claude/claude_native)"
  type        = string
  default     = "us-east5"
}

variable "anthropic_api_key" {
  description = "Solo si agent_model_provider = anthropic"
  type        = string
  default     = ""
  sensitive   = true
}

# ---------- A2UI ----------
variable "a2ui_enabled" {
  description = "Inyecta el contrato A2UI en el orquestador y despliega su superficie A2A"
  type        = bool
  default     = true
}

variable "deploy_orchestrator_a2a_surface" {
  description = "Despliega también el orquestador en Cloud Run como servidor A2A+A2UI para un frontend propio"
  type        = bool
  default     = true
}
