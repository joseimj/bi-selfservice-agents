output "orchestrator_reasoning_engine" {
  description = "ID del Reasoning Engine (Agent Engine) del orquestador"
  value       = google_vertex_ai_reasoning_engine.orchestrator.id
}

output "catalog_agent_url" {
  value = google_cloud_run_v2_service.specialist["catalog"].uri
}

output "builder_agent_url" {
  value = google_cloud_run_v2_service.specialist["builder"].uri
}

output "render_agent_url" {
  value = google_cloud_run_v2_service.specialist["render"].uri
}

output "orchestrator_a2a_url" {
  description = "Endpoint A2A+A2UI del orquestador (AgentCard en /.well-known/agent-card.json)"
  value       = var.deploy_orchestrator_a2a_surface ? google_cloud_run_v2_service.orchestrator_a2a[0].uri : null
}

output "agents_service_account" {
  value = google_service_account.agents.email
}

output "excel_agent_url" {
  value = google_cloud_run_v2_service.specialist["excel"].uri
}

output "deliverables_agent_url" {
  description = "Puerta única de la subcuadrilla de formatos (Excel/CSV, Slides, Docs, PDF)"
  value       = google_cloud_run_v2_service.specialist["deliverables"].uri
}
