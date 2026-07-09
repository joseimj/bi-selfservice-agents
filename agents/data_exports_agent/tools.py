"""Tools del Data Exports Agent: formatos machine-readable (JSON, Parquet, Avro).

Diferencia clave con el agente Tabular: aquí el consumidor es un SISTEMA, no
una persona. La fidelidad de tipos importa más que el formato visual, así que
el esquema NO se adivina desde los datos: se construye desde la metadata de
LookML (el Catalog conoce el tipo de cada campo). Un Parquet con todo string
es un Parquet malo.

Volumen: ruta por API con tope de filas (default 100k). Para volúmenes
mayores, la evolución documentada es delegar a BigQuery el EXPORT DATA
(format='PARQUET') usando el SQL que Looker genera para el query — los datos
no pasarían por el agente. Requiere bigquery.jobUser; ver roadmap.

Tipos temporales: se entregan como strings ISO (decisión deliberada de
portabilidad; el consumidor los castea con su propio timezone handling).
"""
import io
import json

import looker_sdk.sdk.api40.models as models40

from common.delivery import SIGNED_URL_HOURS, timestamped_name, upload_and_sign
from common.looker_client import get_sdk

MAX_ROWS = 100_000

# LookML type -> tipo lógico portable
_INT_TYPES = {"count", "count_distinct", "sum_int", "int", "integer"}
_FLOAT_TYPES = {"number", "sum", "average", "avg", "median", "min", "max",
                "percent_of_total", "decimal"}
_BOOL_TYPES = {"yesno", "boolean"}


def _looker_field_types(model: str, explore: str, fields: list[str]) -> dict:
    """Tipos de campo desde la metadata LookML (no desde los datos)."""
    sdk = get_sdk()
    ex = sdk.lookml_model_explore(
        lookml_model_name=model, explore_name=explore,
        fields="fields(dimensions(name,type),measures(name,type))")
    catalog = {}
    for coll in (ex.fields.dimensions or []), (ex.fields.measures or []):
        for f in coll:
            catalog[f.name] = (f.type or "string").lower()
    out = {}
    for name in fields:
        t = catalog.get(name, "string")
        if t in _INT_TYPES:
            out[name] = "int"
        elif t in _FLOAT_TYPES:
            out[name] = "float"
        elif t in _BOOL_TYPES:
            out[name] = "bool"
        else:
            out[name] = "string"  # fechas incluidas: ISO strings, deliberado
    return out


def _coerce(rows: list[dict], schema: dict) -> list[dict]:
    def cast(v, t):
        if v is None:
            return None
        try:
            if t == "int":
                return int(v)
            if t == "float":
                return float(v)
            if t == "bool":
                return v if isinstance(v, bool) else str(v).lower() in ("yes", "true", "1")
        except (TypeError, ValueError):
            return None
        return str(v)
    return [{k: cast(r.get(k), schema[k]) for k in schema} for r in rows]


def _run_rows(model: str, explore: str, fields: list[str],
              filters: dict | None, sorts: list[str] | None, limit: int) -> list[dict]:
    sdk = get_sdk()
    q = models40.WriteQuery(model=model, view=explore, fields=fields,
                            filters=filters or {}, sorts=sorts or [],
                            limit=str(min(limit, MAX_ROWS)))
    raw = sdk.run_inline_query(result_format="json", body=q)
    return json.loads(raw) if isinstance(raw, str) else raw


def _result(url: str, fmt: str, rows: int, schema: dict | None = None) -> str:
    out = {"download_url": url, "format": fmt, "rows": rows,
           "expires_in_hours": SIGNED_URL_HOURS,
           "truncated": rows >= MAX_ROWS}
    if schema:
        out["schema"] = schema
    return json.dumps(out, ensure_ascii=False)


def export_query_to_json(model: str, explore: str, fields: list[str],
                         filename: str, filters: dict | None = None,
                         sorts: list[str] | None = None, limit: int = 100000) -> str:
    """Exporta un query a JSON (array de objetos, tipos coercidos según LookML)."""
    schema = _looker_field_types(model, explore, fields)
    rows = _coerce(_run_rows(model, explore, fields, filters, sorts, limit), schema)
    data = json.dumps(rows, ensure_ascii=False).encode()
    url = upload_and_sign(data, timestamped_name(filename, ".json"))
    return _result(url, "json", len(rows), schema)


def export_query_to_parquet(model: str, explore: str, fields: list[str],
                            filename: str, filters: dict | None = None,
                            sorts: list[str] | None = None, limit: int = 100000) -> str:
    """Exporta un query a Parquet (esquema Arrow construido desde LookML)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema = _looker_field_types(model, explore, fields)
    rows = _coerce(_run_rows(model, explore, fields, filters, sorts, limit), schema)
    arrow_types = {"int": pa.int64(), "float": pa.float64(),
                   "bool": pa.bool_(), "string": pa.string()}
    pa_schema = pa.schema([(k, arrow_types[t]) for k, t in schema.items()])
    table = pa.Table.from_pylist(rows, schema=pa_schema)
    buf = io.BytesIO()
    pq.write_table(table, buf, compression="snappy")
    url = upload_and_sign(buf.getvalue(), timestamped_name(filename, ".parquet"))
    return _result(url, "parquet", len(rows), schema)


def export_query_to_avro(model: str, explore: str, fields: list[str],
                         filename: str, filters: dict | None = None,
                         sorts: list[str] | None = None, limit: int = 100000) -> str:
    """Exporta un query a Avro (schema record construido desde LookML)."""
    import fastavro
    schema = _looker_field_types(model, explore, fields)
    rows = _coerce(_run_rows(model, explore, fields, filters, sorts, limit), schema)
    avro_types = {"int": "long", "float": "double", "bool": "boolean", "string": "string"}
    avro_schema = {
        "type": "record", "name": "LookerExport", "namespace": "bi.selfservice",
        "fields": [{"name": k.replace(".", "_"), "type": ["null", avro_types[t]]}
                   for k, t in schema.items()],
    }
    records = [{k.replace(".", "_"): v for k, v in r.items()} for r in rows]
    buf = io.BytesIO()
    fastavro.writer(buf, fastavro.parse_schema(avro_schema), records)
    url = upload_and_sign(buf.getvalue(), timestamped_name(filename, ".avro"))
    return _result(url, "avro", len(rows), schema)


ALL_TOOLS = [export_query_to_json, export_query_to_parquet, export_query_to_avro]
