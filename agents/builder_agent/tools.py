"""Tools de escritura: aquí ocurre el autoservicio real.

A diferencia del patrón 'agente que renderiza imágenes', estas tools
MATERIALIZAN dashboards nativos en Looker vía la API 4.0:

  create_query -> create_dashboard -> create_dashboard_element -> layout

El resultado es un dashboard user-defined real, editable en Looker,
con filtros cross-tile y layout tipo newspaper (grid de 24 columnas).
"""
import json
import os

import looker_sdk.sdk.api40.models as models40

from common.looker_client import get_sdk

GRID_COLS = 24          # ancho total del layout newspaper de Looker
DEFAULT_TILE_W = 12     # 2 tiles por fila
DEFAULT_TILE_H = 8

VALID_VIS = {
    "looker_column", "looker_bar", "looker_line", "looker_area",
    "looker_pie", "looker_scatter", "looker_grid", "single_value",
    "looker_map", "looker_donut_multiples", "table",
}


def create_dashboard(title: str, description: str = "", folder_id: str = "") -> str:
    """Crea un dashboard vacío. Devuelve su id y URL. Usa el folder compartido por defecto."""
    sdk = get_sdk()
    folder = folder_id or os.environ.get("LOOKER_TARGET_FOLDER_ID") or None
    db = sdk.create_dashboard(models40.WriteDashboard(
        title=title, description=description, folder_id=folder,
        preferred_viewer="dashboards-next",
    ))
    base = os.environ.get("LOOKERSDK_BASE_URL", "").rstrip("/").removesuffix(":19999")
    return json.dumps({"dashboard_id": db.id, "title": db.title,
                       "url": f"{base}/dashboards/{db.id}"})


def add_tile(dashboard_id: str, title: str, model: str, explore: str,
             fields: list[str], vis_type: str = "looker_column",
             filters: dict | None = None, sorts: list[str] | None = None,
             pivots: list[str] | None = None, limit: int = 500) -> str:
    """Agrega un tile (query + visualización) a un dashboard existente.

    fields: nombres exactos view.field validados por el Catalog Agent.
    vis_type: looker_column|looker_bar|looker_line|looker_area|looker_pie|
              looker_scatter|looker_grid|single_value|table
    """
    if vis_type not in VALID_VIS:
        return json.dumps({"error": f"vis_type inválido. Usa uno de: {sorted(VALID_VIS)}"})
    sdk = get_sdk()
    q = sdk.create_query(models40.WriteQuery(
        model=model, view=explore, fields=fields,
        filters=filters or {}, sorts=sorts or [], pivots=pivots or [],
        limit=str(limit), vis_config={"type": vis_type},
    ))
    el = sdk.create_dashboard_element(models40.WriteDashboardElement(
        dashboard_id=dashboard_id, query_id=q.id, type="vis", title=title,
        title_hidden=False,
    ))
    return json.dumps({"element_id": el.id, "query_id": q.id, "title": title})


def add_text_tile(dashboard_id: str, title: str, body_markdown: str = "") -> str:
    """Agrega un tile de texto/markdown (títulos de sección, notas)."""
    sdk = get_sdk()
    el = sdk.create_dashboard_element(models40.WriteDashboardElement(
        dashboard_id=dashboard_id, type="text",
        title_text=title, body_text=body_markdown,
    ))
    return json.dumps({"element_id": el.id, "type": "text"})


def add_dashboard_filter(dashboard_id: str, name: str, model: str, explore: str,
                         dimension: str, default_value: str = "") -> str:
    """Crea un filtro a nivel dashboard (ej. País, Rango de fechas) sobre una dimensión."""
    sdk = get_sdk()
    f = sdk.create_dashboard_filter(models40.WriteCreateDashboardFilter(
        dashboard_id=dashboard_id, name=name, title=name, type="field_filter",
        model=model, explore=explore, dimension=dimension,
        default_value=default_value or None, allow_multiple_values=True, row=0,
    ))
    return json.dumps({"filter_id": f.id, "name": f.name})


def wire_filter_to_tiles(dashboard_id: str, filter_name: str, dimension: str) -> str:
    """Conecta un filtro del dashboard a todos los tiles cuyo explore contenga la dimensión."""
    sdk = get_sdk()
    db = sdk.dashboard(dashboard_id=dashboard_id, fields="dashboard_elements")
    wired = []
    for el in (db.dashboard_elements or []):
        if el.type != "vis":
            continue
        try:
            filt = (el.result_maker.filterables or [None])[0] if el.result_maker else None
            sdk.update_dashboard_element(
                dashboard_element_id=el.id,
                body=models40.WriteDashboardElement(
                    result_maker=models40.ResultMakerWithIdVisConfigAndDynamicFields(
                        filterables=[models40.ResultMakerFilterables(
                            model=filt.model if filt else None,
                            view=filt.view if filt else None,
                            listen=[models40.ResultMakerFilterablesListen(
                                dashboard_filter_name=filter_name, field=dimension)],
                        )]
                    )
                ),
            )
            wired.append(el.id)
        except Exception:  # el tile puede no ser filtrable por esa dimensión
            continue
    return json.dumps({"filter": filter_name, "wired_elements": wired})


def apply_grid_layout(dashboard_id: str, columns_per_row: int = 2) -> str:
    """Reorganiza los tiles en un grid uniforme (newspaper, 24 cols).

    columns_per_row: 1 (tiles full-width), 2 (12+12), 3 (8+8+8) o 4 (6x4).
    """
    if columns_per_row not in (1, 2, 3, 4):
        return json.dumps({"error": "columns_per_row debe ser 1..4"})
    w = GRID_COLS // columns_per_row
    sdk = get_sdk()
    db = sdk.dashboard(dashboard_id=dashboard_id, fields="dashboard_layouts")
    layout = (db.dashboard_layouts or [None])[0]
    if not layout:
        return json.dumps({"error": "El dashboard no tiene layout"})
    comps = sdk.dashboard_layout_dashboard_layout_components(dashboard_layout_id=layout.id)
    for i, comp in enumerate(comps):
        row, col = divmod(i, columns_per_row)
        sdk.update_dashboard_layout_component(
            dashboard_layout_component_id=comp.id,
            body=models40.WriteDashboardLayoutComponent(
                row=row * DEFAULT_TILE_H, column=col * w,
                width=w, height=DEFAULT_TILE_H,
            ),
        )
    return json.dumps({"layout_id": layout.id, "tiles": len(comps),
                       "grid": f"{columns_per_row} por fila"})


def get_dashboard_spec(dashboard_id: str) -> str:
    """Devuelve la estructura actual del dashboard (tiles, filtros) para revisión."""
    sdk = get_sdk()
    db = sdk.dashboard(dashboard_id=dashboard_id,
                       fields="id,title,dashboard_elements,dashboard_filters")
    return json.dumps({
        "id": db.id, "title": db.title,
        "tiles": [{"id": e.id, "title": e.title, "type": e.type}
                  for e in (db.dashboard_elements or [])],
        "filters": [{"id": f.id, "name": f.name, "dimension": f.dimension}
                    for f in (db.dashboard_filters or [])],
    }, ensure_ascii=False)


def delete_tile(dashboard_element_id: str) -> str:
    """Elimina un tile de un dashboard (para iterar sobre el diseño)."""
    sdk = get_sdk()
    sdk.delete_dashboard_element(dashboard_element_id=dashboard_element_id)
    return json.dumps({"deleted": dashboard_element_id})


def delete_dashboard(dashboard_id: str) -> str:
    """Envía un dashboard a la papelera (soft delete). Solo si el usuario lo confirma."""
    sdk = get_sdk()
    sdk.update_dashboard(dashboard_id=dashboard_id,
                         body=models40.WriteDashboard(deleted=True))
    return json.dumps({"soft_deleted": dashboard_id})


ALL_TOOLS = [create_dashboard, add_tile, add_text_tile, add_dashboard_filter,
             wire_filter_to_tiles, apply_grid_layout, get_dashboard_spec,
             delete_tile, delete_dashboard]
