"""Cliente Looker SDK 4.0 compartido por todos los agentes.

Credenciales vía env vars estándar del SDK:
  LOOKERSDK_BASE_URL, LOOKERSDK_CLIENT_ID, LOOKERSDK_CLIENT_SECRET
(inyectadas por Terraform desde Secret Manager).
"""
import functools
import os

import looker_sdk


@functools.lru_cache(maxsize=1)
def get_sdk():
    os.environ.setdefault("LOOKERSDK_VERIFY_SSL", "true")
    os.environ.setdefault("LOOKERSDK_TIMEOUT", "120")
    return looker_sdk.init40()


def allowed_models() -> list[str]:
    """Modelos LookML que el agente puede usar (allowlist)."""
    import json
    raw = os.environ.get("LOOKER_MODELS", "[]")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return [m.strip() for m in raw.strip("[]").split(",") if m.strip()]


def poll_render_task(sdk, task_id: str, timeout_s: int = 120) -> bytes:
    """Espera un render task de Looker y devuelve los bytes del resultado."""
    import time
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        t = sdk.render_task(render_task_id=task_id)
        if t.status == "success":
            return sdk.render_task_results(render_task_id=task_id)
        if t.status == "failure":
            raise RuntimeError(f"render task falló: {t.status_detail}")
        time.sleep(3)
    raise TimeoutError("render task no terminó a tiempo")
