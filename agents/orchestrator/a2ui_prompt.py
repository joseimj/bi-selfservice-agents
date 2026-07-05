"""Contrato A2UI del orquestador.

A2UI (protocolo de UI generativa de Google) permite que el agente devuelva
BLUEPRINTS de componentes nativos (JSON declarativo), no HTML ni código.
El host (frontend Lit/Angular/Flutter) los renderiza con su propio estilo.

El A2uiSchemaManager inyecta en el system prompt el catálogo de componentes,
el schema JSON y ejemplos few-shot, para que el LLM emita A2UI válido.

Transporte: los payloads viajan como A2A DataPart con MIME
application/json+a2ui, por lo que el mismo agente sirve texto plano en
Gemini Enterprise y UI rica en el frontend A2UI sin bifurcar la lógica.
"""
import os

ROLE_DESCRIPTION = """Eres el Looker Self-Service Orchestrator: conviertes peticiones en
lenguaje natural en dashboards NATIVOS de Looker, coordinando agentes especialistas
vía A2A (catálogo semántico, construcción de dashboards, render/QA)."""

UI_DESCRIPTION = """Usa A2UI para hacer el autoservicio guiado:
1. WIZARD DE SPEC: cuando el usuario pida un dashboard, muestra un Card con:
   - selector (List/MultipleChoice) de explore (opciones reales del Catalog Agent),
   - MultipleChoice de dimensiones y medidas disponibles,
   - selector de tipo de gráfico por tile (column, bar, line, pie, single_value, table),
   - TextField para el título y Slider/selector para columnas del layout (1-4),
   - Button "Crear dashboard" que envía el spec.
2. PREVIEW: tras construir, muestra un Card con el título, la lista de tiles creados,
   la Image del render (si hay URL) y dos Buttons: "Abrir en Looker" (link firmado)
   y "Ajustar" (reabre el wizard con el spec actual).
3. CONFIRMACIONES DESTRUCTIVAS: eliminar un dashboard SIEMPRE pasa por un Card de
   confirmación con Buttons Confirmar/Cancelar.
Nunca hardcodees datos en los componentes: usa path bindings al data model."""


def build_instruction(base_instruction: str) -> str:
    """Devuelve la instrucción final; con A2UI habilitado, incluye el contrato completo."""
    if os.environ.get("A2UI_ENABLED", "false").lower() != "true":
        return base_instruction
    try:
        from a2ui.core.schema.manager import A2uiSchemaManager
        from a2ui.basic_catalog.provider import BasicCatalog
        schema_manager = A2uiSchemaManager(catalogs=[BasicCatalog.get_config()])
        return schema_manager.generate_system_prompt(
            role_description=ROLE_DESCRIPTION + "\n\n" + base_instruction,
            ui_description=UI_DESCRIPTION,
            include_schema=True,
            include_examples=True,
        )
    except ImportError:
        # SDK de A2UI no instalado: degrada a texto sin romper el agente.
        return base_instruction
