"""Acceso a templates organizacionales publicados en GCS.

Layout en el bucket (Terraform los sube desde templates/ del repo):
  templates/dashboards/<id>.yaml   -> DashboardSpec parametrizado ({{ placeholder }})
  templates/excel/<nombre>.xlsx    -> workbook base con branding corporativo

Gobernanza: los templates se versionan en el repositorio y se publican en cada
`terraform apply`; cambiar un template = pull request, no un ajuste manual.
"""
import functools
import os
import re

PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@functools.lru_cache(maxsize=1)
def _bucket():
    from google.cloud import storage
    return storage.Client().bucket(os.environ["TEMPLATES_BUCKET"])


def _prefix(kind: str) -> str:
    return f"{os.environ.get('TEMPLATES_PREFIX', 'templates')}/{kind}/"


def list_names(kind: str) -> list[str]:
    """Nombres disponibles de templates de un tipo ('dashboards' | 'excel')."""
    p = _prefix(kind)
    return [b.name.removeprefix(p) for b in _bucket().list_blobs(prefix=p)
            if b.name != p]


def load_bytes(kind: str, name: str) -> bytes:
    return _bucket().blob(_prefix(kind) + name).download_as_bytes()


def load_dashboard_template(template_id: str) -> dict:
    import yaml
    name = template_id if template_id.endswith((".yaml", ".yml")) else f"{template_id}.yaml"
    return yaml.safe_load(load_bytes("dashboards", name))


def render_placeholders(obj, params: dict):
    """Sustituye {{ placeholder }} recursivamente en el spec del template."""
    if isinstance(obj, str):
        def sub(m):
            key = m.group(1)
            if key not in params:
                raise KeyError(key)
            return str(params[key])
        return PLACEHOLDER.sub(sub, obj)
    if isinstance(obj, list):
        return [render_placeholders(x, params) for x in obj]
    if isinstance(obj, dict):
        return {k: render_placeholders(v, params) for k, v in obj.items()}
    return obj


def missing_params(template: dict, params: dict) -> list[str]:
    """Placeholders declarados u ocurrentes en el spec que faltan en params."""
    declared = {p["name"] for p in template.get("params", [])}
    found = set()

    def scan(o):
        if isinstance(o, str):
            found.update(PLACEHOLDER.findall(o))
        elif isinstance(o, list):
            for x in o:
                scan(x)
        elif isinstance(o, dict):
            for v in o.values():
                scan(v)

    scan(template.get("spec", {}))
    defaults = {p["name"] for p in template.get("params", []) if "default" in p}
    return sorted((declared | found) - set(params) - defaults)


def apply_defaults(template: dict, params: dict) -> dict:
    out = {p["name"]: p["default"] for p in template.get("params", []) if "default" in p}
    out.update(params)
    return out
