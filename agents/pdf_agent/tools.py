"""Tools del PDF Agent: dos rutas deliberadas.

1. NATIVA (barata, primera opción): Looker ya renderiza dashboards a PDF
   (dashboard render task con result_format='pdf'). Para "mándame el
   dashboard en PDF" no hay que componer nada.
2. COMPUESTA (ReportLab): documentos a la medida — portada, narrativa por
   secciones y, opcionalmente, las visualizaciones de un dashboard como
   imágenes. Solo cuando la ruta nativa no alcanza.
"""
import io
import json

import looker_sdk.sdk.api40.models as models40
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, SimpleDocTemplate,
                                Spacer)

from common.delivery import SIGNED_URL_HOURS, timestamped_name, upload_and_sign
from common.looker_client import get_sdk, poll_render_task

PAGE_W, PAGE_H = LETTER
ACCENT = colors.HexColor("#1F4E79")


def export_dashboard_to_pdf(dashboard_id: str, filename: str = "",
                            width: int = 1200, height: int = 1600) -> str:
    """Ruta NATIVA: PDF del dashboard renderizado por Looker (fiel al layout
    y a las visualizaciones). Úsala por defecto para 'el dashboard en PDF'."""
    sdk = get_sdk()
    db = sdk.dashboard(dashboard_id=dashboard_id, fields="id,title")
    task = sdk.create_dashboard_render_task(
        dashboard_id=dashboard_id, result_format="pdf",
        body=models40.CreateDashboardRenderTask(dashboard_style="tiled",
                                                dashboard_filters=None),
        width=width, height=height)
    pdf = poll_render_task(sdk, task.id, timeout_s=180)
    url = upload_and_sign(pdf, timestamped_name(filename or db.title or "dashboard", ".pdf"))
    return json.dumps({"download_url": url, "route": "native",
                       "expires_in_hours": SIGNED_URL_HOURS})


def compose_pdf_document(title: str, sections: list[dict], filename: str = "",
                         dashboard_id: str = "", subtitle: str = "") -> str:
    """Ruta COMPUESTA: documento a la medida. Cada sección: {"heading": str,
    "body": str}. Si se pasa dashboard_id, agrega al final las visualizaciones
    de sus tiles como imágenes (anexo gráfico)."""
    styles = getSampleStyleSheet()
    h_title = ParagraphStyle("T", parent=styles["Title"], textColor=ACCENT, fontSize=26)
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=ACCENT)
    body = styles["BodyText"]

    story = [Spacer(1, 2.2 * inch), Paragraph(title, h_title)]
    if subtitle:
        story.append(Paragraph(subtitle, styles["Italic"]))
    story.append(PageBreak())

    for s in sections:
        story.append(Paragraph(s.get("heading", ""), h1))
        for para in (s.get("body") or "").split("\n\n"):
            if para.strip():
                story.append(Paragraph(para.strip(), body))
        story.append(Spacer(1, 0.2 * inch))

    appended = []
    if dashboard_id:
        sdk = get_sdk()
        db = sdk.dashboard(dashboard_id=dashboard_id, fields="dashboard_elements")
        story.append(PageBreak())
        story.append(Paragraph("Anexo gráfico", h1))
        for el in (db.dashboard_elements or []):
            if el.type != "vis" or not el.query_id:
                continue
            try:
                task = sdk.create_query_render_task(query_id=el.query_id,
                                                    result_format="png",
                                                    width=1200, height=700)
                png = poll_render_task(sdk, task.id)
                story.append(Paragraph(el.title or "", styles["Heading2"]))
                story.append(Image(io.BytesIO(png), width=6.5 * inch,
                                   height=6.5 * inch * 700 / 1200))
                story.append(Spacer(1, 0.25 * inch))
                appended.append(el.title or el.id)
            except Exception:
                continue

    buf = io.BytesIO()
    SimpleDocTemplate(buf, pagesize=LETTER, topMargin=0.9 * inch,
                      bottomMargin=0.9 * inch).build(story)
    url = upload_and_sign(buf.getvalue(), timestamped_name(filename or title, ".pdf"))
    return json.dumps({"download_url": url, "route": "composed",
                       "sections": len(sections), "appendix_tiles": appended,
                       "expires_in_hours": SIGNED_URL_HOURS}, ensure_ascii=False)


ALL_TOOLS = [export_dashboard_to_pdf, compose_pdf_document]
