"""
PDF Invoice Exporter — EduVision
Uses: reportlab (already in requirements)
QR Code: generated via reportlab's own shapes (no external QR lib needed)
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


# ── Colors ────────────────────────────────────────────────────
NAVY   = colors.HexColor("#0F2D6B")
BLUE   = colors.HexColor("#1D4ED8")
LIGHT  = colors.HexColor("#EFF6FF")
GRAY   = colors.HexColor("#6B7280")
GREEN  = colors.HexColor("#16A34A")
RED    = colors.HexColor("#DC2626")
WHITE  = colors.white
BLACK  = colors.black


def _draw_qr(c: canvas.Canvas, data: str, x: float, y: float, size: float = 28 * mm):
    """Draw a QR code at (x, y) with given size using reportlab's built-in QR widget."""
    try:
        qr = QrCodeWidget(data)
        bounds = qr.getBounds()
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
        d.add(qr)
        renderPDF.draw(d, c, x, y)
    except Exception:
        # Fallback: draw a placeholder box
        c.setStrokeColor(NAVY)
        c.setFillColor(LIGHT)
        c.rect(x, y, size, size, fill=1, stroke=1)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(x + size / 2, y + size / 2, "QR")


def generate_invoice_pdf(invoice: dict) -> bytes:
    """
    Generate a printable A4 invoice PDF.

    invoice dict keys (from sales_invoices table):
        invoice_number, student_name, student_phone,
        subtotal, discount_pct, discount_amount, total_amount,
        payment_method, status, notes, created_at,
        cashier_id (optional), refund_reason (optional)
    """
    buf = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)

    margin_l = 18 * mm
    margin_r = page_w - 18 * mm
    content_w = margin_r - margin_l

    # ── Header band ──────────────────────────────────────────
    c.setFillColor(NAVY)
    c.rect(0, page_h - 38 * mm, page_w, 38 * mm, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 22)
    c.drawString(margin_l, page_h - 18 * mm, "EduVision")

    c.setFont("Helvetica", 10)
    c.drawString(margin_l, page_h - 25 * mm, "منصة التعليم الإلكتروني")

    # Invoice label on the right
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(margin_r, page_h - 16 * mm, "INVOICE / فاتورة")

    inv_num = invoice.get("invoice_number", "—")
    c.setFont("Helvetica", 10)
    c.drawRightString(margin_r, page_h - 23 * mm, f"# {inv_num}")

    date_str = str(invoice.get("created_at", ""))[:10]
    c.drawRightString(margin_r, page_h - 30 * mm, date_str)

    # ── Status badge ─────────────────────────────────────────
    status = invoice.get("status", "paid")
    badge_color = {"paid": GREEN, "pending": colors.orange, "refunded": RED}.get(status, GRAY)
    badge_label = {"paid": "PAID ✓", "pending": "PENDING", "refunded": "REFUNDED"}.get(status, status.upper())

    c.setFillColor(badge_color)
    c.roundRect(margin_r - 28 * mm, page_h - 36 * mm, 28 * mm, 8 * mm, 2 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(margin_r - 14 * mm, page_h - 32.5 * mm, badge_label)

    # ── Student info ─────────────────────────────────────────
    y = page_h - 52 * mm

    c.setFillColor(LIGHT)
    c.rect(margin_l, y - 4 * mm, content_w, 18 * mm, fill=1, stroke=0)

    c.setFillColor(NAVY)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin_l + 4 * mm, y + 10 * mm, "بيانات الطالب / Student Info")

    c.setFillColor(BLACK)
    c.setFont("Helvetica", 10)
    c.drawString(margin_l + 4 * mm, y + 4 * mm,
                 f"الاسم: {invoice.get('student_name', '—')}")
    c.drawString(margin_l + 4 * mm, y,
                 f"الهاتف: {invoice.get('student_phone', '—')}")

    # ── Items table ───────────────────────────────────────────
    y -= 18 * mm

    data = [
        ["البيان", "القيمة"],
        ["المبلغ الأساسي (Subtotal)",
         f"{invoice.get('subtotal', 0):,.2f} ج.م"],
        [f"خصم {invoice.get('discount_pct', 0):.0f}% (Discount)",
         f"- {invoice.get('discount_amount', 0):,.2f} ج.م"],
        ["طريقة الدفع (Payment Method)",
         str(invoice.get("payment_method", "cash")).replace("_", " ").title()],
    ]

    if invoice.get("notes"):
        data.append(["ملاحظات (Notes)", invoice["notes"]])

    col_widths = [content_w * 0.65, content_w * 0.35]
    tbl = Table(data, colWidths=col_widths)
    tbl.setStyle(TableStyle([
        # Header row
        ("BACKGROUND",  (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",   (0, 0), (-1, 0), WHITE),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 10),
        ("ALIGN",       (0, 0), (-1, 0), "CENTER"),
        # Body
        ("FONTNAME",    (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",    (0, 1), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ("ALIGN",       (1, 1), (1, -1), "RIGHT"),
        ("ALIGN",       (0, 1), (0, -1), "LEFT"),
        # Grid
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))

    tbl.wrapOn(c, content_w, page_h)
    tbl_h = tbl._height
    tbl.drawOn(c, margin_l, y - tbl_h)
    y -= tbl_h + 6 * mm

    # ── Total box ─────────────────────────────────────────────
    total = invoice.get("total_amount", 0)
    box_h = 14 * mm
    box_x = margin_r - 70 * mm

    c.setFillColor(NAVY)
    c.roundRect(box_x, y - box_h, 70 * mm, box_h, 3 * mm, fill=1, stroke=0)

    c.setFillColor(WHITE)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(box_x + 5 * mm, y - 9 * mm, "الإجمالي / Total:")
    c.setFont("Helvetica-Bold", 15)
    c.drawRightString(margin_r - 3 * mm, y - 9.5 * mm, f"{total:,.2f} ج.م")

    y -= box_h + 8 * mm

    # ── QR Code ───────────────────────────────────────────────
    qr_size = 28 * mm
    qr_data = (
        f"EduVision Invoice\n"
        f"#{inv_num}\n"
        f"Student: {invoice.get('student_name', '')}\n"
        f"Total: {total} EGP\n"
        f"Date: {date_str}\n"
        f"Status: {status}"
    )
    _draw_qr(c, qr_data, margin_l, y - qr_size, qr_size)

    c.setFillColor(GRAY)
    c.setFont("Helvetica", 8)
    c.drawString(margin_l, y - qr_size - 5 * mm, "امسح QR للتحقق من الفاتورة")

    # Refund note
    if status == "refunded" and invoice.get("refund_reason"):
        c.setFillColor(RED)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(margin_l + qr_size + 6 * mm, y - 8 * mm,
                     f"تم الرد — السبب: {invoice['refund_reason']}")

    # ── Footer ────────────────────────────────────────────────
    c.setFillColor(NAVY)
    c.rect(0, 0, page_w, 12 * mm, fill=1, stroke=0)
    c.setFillColor(WHITE)
    c.setFont("Helvetica", 8)
    c.drawCentredString(page_w / 2, 5 * mm,
                        f"EduVision LMS — eduvision.app | Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()
