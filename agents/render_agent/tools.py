"""Tools de verificación visual y entrega: render PNG + embed SSO firmado.

Cierra el loop de calidad: después de que el Builder crea el dashboard,
este agente lo renderiza para que el usuario lo VEA en el chat y entrega
un link interactivo firmado por Looker.
"""
import json
import os
import time

import looker_sdk.sdk.api40.models as models40

from common.looker_client import get_sdk

RENDER_TIMEOUT_S = 120


def render_dashboard_png(dashboard_id: str, width: int = 1200, height: int = 900,
                         filters: dict | None = None) -> dict:
    """Renderiza un dashboard como PNG. Devuelve bytes en base64 para artifact."""
    import base64
    sdk = get_sdk()
    target = dashboard_id
    if filters:
        from urllib.parse import urlencode
        target = f"{dashboard_id}?{urlencode(filters)}"
    task = sdk.create_dashboard_render_task(
        dashboard_id=target, result_format="png",
        body=models40.CreateDashboardRenderTask(
            dashboard_style="tiled", dashboard_filters=None),
        width=width, height=height,
    )
    deadline = time.time() + RENDER_TIMEOUT_S
    while time.time() < deadline:
        t = sdk.render_task(render_task_id=task.id)
        if t.status == "success":
            png = sdk.render_task_results(render_task_id=task.id)
            return {"status": "ok", "png_base64": base64.b64encode(png).decode()}
        if t.status == "failure":
            return {"status": "error", "detail": t.status_detail}
        time.sleep(3)
    return {"status": "error", "detail": "timeout de render"}


def get_signed_embed_url(dashboard_id: str, external_user_id: str = "selfservice-user",
                         session_length_s: int = 3600) -> str:
    """Genera un URL de embed SSO firmado por Looker para abrir el dashboard interactivo."""
    sdk = get_sdk()
    base = os.environ.get("LOOKERSDK_BASE_URL", "").rstrip("/").removesuffix(":19999")
    url = sdk.create_sso_embed_url(models40.EmbedSsoParams(
        target_url=f"{base}/embed/dashboards/{dashboard_id}",
        session_length=session_length_s,
        external_user_id=external_user_id,
        permissions=["access_data", "see_looks", "see_user_dashboards", "see_lookml_dashboards"],
        models=json.loads(os.environ.get("LOOKER_MODELS", "[]")),
        force_logout_login=True,
    ))
    return json.dumps({"signed_url": url.url})


ALL_TOOLS = [render_dashboard_png, get_signed_embed_url]
