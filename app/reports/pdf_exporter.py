"""
PDF Invoice exporter using ReportLab.
Generates a printable A4 invoice with QR code.
"""
import io
import qrcode
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


# Brand colors
BLUE      = colors.HexColor("#0F2D6B")
LIGHT_BLUE= colors.HexColor("#3B82F6")
GRAY      = colors.HexColor("#6B7280")
LIGHT_GRAY= colors.HexColor("#F3F4F6")
GREEN     = colors.HexColor("#16A34A")
RED       = colors.HexColor("#DC2626")
WHITE     = colors.white
BLACK     = colors.HexColor("#111827")


def _make_qr(data: str) -> io.BytesIO:
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def generate_invoice_pdf(invoice: dict) -> bytes:
    """
    Generate a printable PDF invoice.
    invoice dict keys:
      invoice_number, student_name, student_phone, payment_method,
      total_amount, discount_pct, discount_amount, subtotal,
      status, created_at, notes,
      items: [{"subject_name", "quantity", "unit_price", "total_price"}]
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle("title", fontSize=22, textColor=BLUE,
                                  alignment=TA_CENTER, fontName="Helvetica-Bold",
                                  spaceAfter=4)
    sub_style   = ParagraphStyle("sub", fontSize=10, textColor=GRAY,
                                  alignment=TA_CENTER, fontName="Helvetica")
    hdr_style   = ParagraphStyle("hdr", fontSize=11, textColor=BLUE,
                                  fontName="Helvetica-Bold")
    body_style  = ParagraphStyle("body", fontSize=10, textColor=BLACK,
                                  fontName="Helvetica")
    small_style = ParagraphStyle("small", fontSize=8, textColor=GRAY,
                                  fontName="Helvetica")

    inv_num    = invoice.get("invoice_number", "—")
    stu_name   = invoice.get("student_name", "—")
    stu_phone  = invoice.get("student_phone", "—")
    pay_method = {"cash":"نقداً","card":"بطاقة","transfer":"تحويل"}.get(
                  invoice.get("payment_method","cash"), invoice.get("payment_method","—"))
    total      = invoice.get("total_amount", 0)
    discount   = invoice.get("discount_pct", 0)
    disc_amt   = invoice.get("discount_amount", 0)
    subtotal   = invoice.get("subtotal", total)
    status     = invoice.get("status", "paid")
    created_at = str(invoice.get("created_at",""))[:19]
    notes      = invoice.get("notes","")
    items      = invoice.get("items") or []

    status_color = GREEN if status=="paid" else RED if status in ("refunded","cancelled") else GRAY
    status_label = {"paid":"مدفوع ✓","refunded":"مسترجع","cancelled":"ملغي","pending":"معلق"}.get(status, status)

    # QR code (invoice number)
    qr_buf = _make_qr(f"EduVision Invoice: {inv_num}\nStudent: {stu_name}\nTotal: {total} EGP")
    qr_img = Image(qr_buf, width=3*cm, height=3*cm)

    elements = []

    # ── HEADER ──────────────────────────────────────────────
    header_data = [[
        Paragraph("<b>EduVision LMS</b>", title_style),
        qr_img,
    ]]
    header_tbl = Table(header_data, colWidths=[13*cm, 3.5*cm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN",  (1,0), (1,0),   "RIGHT"),
    ]))
    elements.append(header_tbl)
    elements.append(Paragraph("منصة التعليم الذكي", sub_style))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(HRFlowable(width="100%", thickness=2, color=BLUE))
    elements.append(Spacer(1, 0.3*cm))

    # ── INVOICE META ─────────────────────────────────────────
    meta_data = [
        [Paragraph(f"<b>رقم الفاتورة:</b> {inv_num}", hdr_style),
         Paragraph(f"<b>التاريخ:</b> {created_at}", body_style)],
        [Paragraph(f"<b>اسم الطالب:</b> {stu_name}", body_style),
         Paragraph(f"<b>الهاتف:</b> {stu_phone or '—'}", body_style)],
        [Paragraph(f"<b>طريقة الدفع:</b> {pay_method}", body_style),
         Paragraph(f"<b>الحالة:</b> <font color='#{status_color.hexval()[2:].upper()}'>{status_label}</font>", body_style)],
    ]
    meta_tbl = Table(meta_data, colWidths=[8.5*cm, 8.5*cm])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), LIGHT_GRAY),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [LIGHT_GRAY, WHITE]),
        ("TOPPADDING",    (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING",   (0,0), (-1,-1), 8),
        ("RIGHTPADDING",  (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#E5E7EB")),
        ("ROUNDEDCORNERS", [4]),
    ]))
    elements.append(meta_tbl)
    elements.append(Spacer(1, 0.5*cm))

    # ── ITEMS TABLE ──────────────────────────────────────────
    elements.append(Paragraph("<b>تفاصيل الفاتورة</b>", hdr_style))
    elements.append(Spacer(1, 0.2*cm))

    tbl_headers = ["#", "المادة", "الكمية", "سعر الوحدة", "الإجمالي"]
    tbl_data    = [[Paragraph(f"<b>{h}</b>", ParagraphStyle("th", fontSize=10,
                               textColor=WHITE, fontName="Helvetica-Bold",
                               alignment=TA_CENTER)) for h in tbl_headers]]

    for i, item in enumerate(items, 1):
        line_total = item.get("total_price") or (item.get("quantity",1) * item.get("unit_price",0))
        tbl_data.append([
            Paragraph(str(i), ParagraphStyle("td", fontSize=10, alignment=TA_CENTER)),
            Paragraph(str(item.get("subject_name","—")), body_style),
            Paragraph(str(item.get("quantity",1)), ParagraphStyle("td", fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"{item.get('unit_price',0):.2f} ج.م", ParagraphStyle("td", fontSize=10, alignment=TA_CENTER)),
            Paragraph(f"{line_total:.2f} ج.م", ParagraphStyle("td", fontSize=10, alignment=TA_CENTER,
                       fontName="Helvetica-Bold")),
        ])

    items_tbl = Table(tbl_data, colWidths=[1*cm, 7*cm, 2*cm, 3.5*cm, 3.5*cm])
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0), (-1,0), BLUE),
        ("ROWBACKGROUNDS",(0,1), (-1,-1), [WHITE, LIGHT_GRAY]),
        ("GRID",          (0,0), (-1,-1), 0.5, colors.HexColor("#E5E7EB")),
        ("TOPPADDING",    (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ("LEFTPADDING",   (0,0), (-1,-1), 6),
        ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
    ]))
    elements.append(items_tbl)
    elements.append(Spacer(1, 0.4*cm))

    # ── TOTALS ───────────────────────────────────────────────
    totals_data = []
    if discount > 0:
        totals_data.append([
            Paragraph("المجموع قبل الخصم:", body_style),
            Paragraph(f"{subtotal:.2f} ج.م", body_style),
        ])
        totals_data.append([
            Paragraph(f"خصم ({discount}%):", body_style),
            Paragraph(f"-{disc_amt:.2f} ج.م", ParagraphStyle("disc", fontSize=10,
                       textColor=RED, fontName="Helvetica")),
        ])

    totals_data.append([
        Paragraph("<b>الإجمالي النهائي:</b>", ParagraphStyle("tot", fontSize=13,
                   textColor=BLUE, fontName="Helvetica-Bold")),
        Paragraph(f"<b>{total:.2f} ج.م</b>", ParagraphStyle("tot", fontSize=13,
                   textColor=BLUE, fontName="Helvetica-Bold", alignment=TA_RIGHT)),
    ])

    totals_tbl = Table(totals_data, colWidths=[12*cm, 5*cm],
                        hAlign="RIGHT")
    totals_tbl.setStyle(TableStyle([
        ("ALIGN",         (1,0), (1,-1), "RIGHT"),
        ("TOPPADDING",    (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
        ("LINEABOVE",     (0,-1), (-1,-1), 1.5, BLUE),
    ]))
    elements.append(totals_tbl)

    # ── NOTES ────────────────────────────────────────────────
    if notes:
        elements.append(Spacer(1, 0.4*cm))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
        elements.append(Spacer(1, 0.2*cm))
        elements.append(Paragraph(f"<b>ملاحظات:</b> {notes}", small_style))

    # ── FOOTER ───────────────────────────────────────────────
    elements.append(Spacer(1, 1*cm))
    elements.append(HRFlowable(width="100%", thickness=1, color=LIGHT_BLUE))
    elements.append(Spacer(1, 0.2*cm))
    elements.append(Paragraph(
        "شكراً لثقتكم في EduVision LMS — منصة التعليم الذكي",
        ParagraphStyle("footer", fontSize=9, textColor=GRAY, alignment=TA_CENTER)
    ))

    doc.build(elements)
    buf.seek(0)
    return buf.read()
