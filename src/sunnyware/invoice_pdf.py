# SPDX-FileCopyrightText: 2026 Shamiur Rashid Sunny
# SPDX-License-Identifier: AGPL-3.0-only
"""Part 216: Invoice PDF Generator."""

import io
import time
from fpdf import FPDF

def generate_invoice_pdf(invoice: dict) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("helvetica", "B", 24)
    pdf.cell(0, 20, "INVOICE", ln=True, align="C")
    
    # Company Info
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5, "Sunnyware SaaS Platform", ln=True, align="C")
    pdf.cell(0, 5, "https://sunnyware.hf.space", ln=True, align="C")
    pdf.ln(10)
    
    # Invoice Details
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(100, 10, f"Invoice ID: {invoice.get('id', 'N/A')}", ln=False)
    raw_ts = invoice.get('created_at') or time.time()
    try:
        import datetime
        dt_str = datetime.datetime.fromtimestamp(float(raw_ts)).strftime("%b %d, %Y")
    except Exception:
        dt_str = str(raw_ts)
    pdf.cell(90, 10, f"Date: {dt_str}", ln=True, align="R")
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(100, 10, f"Customer/Org: {invoice.get('org_id', 'N/A')}", ln=False)
    pdf.cell(90, 10, f"Status: {invoice.get('status', 'paid').upper()}", ln=True, align="R")
    pdf.ln(10)
    
    # Table Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(140, 10, "Description", border=1, fill=True)
    pdf.cell(50, 10, "Amount", border=1, fill=True, align="R")
    pdf.ln()
    
    # Table Body
    pdf.set_font("helvetica", "", 12)
    desc = invoice.get("description", "Subscription Payment")
    amt = invoice.get("amount_cents", 0) / 100.0
    
    pdf.cell(140, 10, desc[:60], border=1)
    pdf.cell(50, 10, f"${amt:.2f}", border=1, align="R")
    pdf.ln()
    
    # Total
    pdf.set_font("helvetica", "B", 14)
    pdf.cell(140, 15, "TOTAL", border=0)
    pdf.cell(50, 15, f"${amt:.2f}", border=0, align="R")
    pdf.ln(20)
    
    # Footer
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 10, "Thank you for your business!", align="C")
    
    return pdf.output()

