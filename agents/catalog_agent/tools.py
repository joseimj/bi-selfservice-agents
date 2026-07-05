"""Tools de descubrimiento semántico: la capa LookML como catálogo.

Este agente es la 'fuente de verdad' para el resto del sistema:
qué modelos, explores y campos existen y cómo se llaman exactamente.
El builder nunca inventa nombres de campos; se los pide a este agente.
"""
import json

from common.looker_client import get_sdk, allowed_models


def list_models() -> str:
    """Lista los modelos LookML accesibles y sus explores."""
    sdk = get_sdk()
    allow = set(allowed_models())
    out = []
    for m in sdk.all_lookml_models(fields="name,label,explores"):
        if allow and m.name not in allow:
            continue
        out.append({
            "model": m.name,
            "label": m.label,
            "explores": [e.name for e in (m.explores or [])],
        })
    return json.dumps(out, ensure_ascii=False)


def list_explores(model: str) -> str:
    """Lista los explores de un modelo LookML."""
    sdk = get_sdk()
    m = sdk.lookml_model(lookml_model_name=model, fields="explores")
    return json.dumps(
        [{"name": e.name, "label": e.label, "description": e.description}
         for e in (m.explores or [])],
        ensure_ascii=False,
    )


def list_fields(model: str, explore: str) -> str:
    """Lista dimensiones y medidas de un explore con su nombre exacto (view.field)."""
    sdk = get_sdk()
    ex = sdk.lookml_model_explore(
        lookml_model_name=model, explore_name=explore,
        fields="fields(dimensions(name,label,type,description),measures(name,label,type,description))",
    )
    f = ex.fields
    return json.dumps({
        "dimensions": [{"name": d.name, "label": d.label, "type": d.type}
                       for d in (f.dimensions or [])],
        "measures": [{"name": m.name, "label": m.label, "type": m.type}
                     for m in (f.measures or [])],
    }, ensure_ascii=False)


def search_dashboards(title: str) -> str:
    """Busca dashboards existentes por título (para reusar en vez de duplicar)."""
    sdk = get_sdk()
    dbs = sdk.search_dashboards(title=f"%{title}%", fields="id,title,folder_id", limit=20)
    return json.dumps([{"id": d.id, "title": d.title, "folder_id": d.folder_id} for d in dbs],
                      ensure_ascii=False)


def preview_query(model: str, explore: str, fields: list[str], filters: dict | None = None,
                  limit: int = 20) -> str:
    """Ejecuta un query ad-hoc y devuelve filas (para validar campos antes de construir)."""
    sdk = get_sdk()
    import looker_sdk.sdk.api40.models as models40
    q = models40.WriteQuery(model=model, view=explore, fields=fields,
                            filters=filters or {}, limit=str(limit))
    result = sdk.run_inline_query(result_format="json", body=q)
    return result if isinstance(result, str) else json.dumps(result)


ALL_TOOLS = [list_models, list_explores, list_fields, search_dashboards, preview_query]
