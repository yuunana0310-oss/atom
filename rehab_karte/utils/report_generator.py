from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import sqlite3
import json
from database.db import get_connection

# Attempt to find a Japanese font
JP_FONT_PATH = "C:\\Windows\\Fonts\\msgothic.ttc" # Common on Windows
if os.path.exists(JP_FONT_PATH):
    pdfmetrics.registerFont(TTFont("MS-Gothic", JP_FONT_PATH))
    FONT_NAME = "MS-Gothic"
else:
    FONT_NAME = "Helvetica" # Fallback (will garble Japanese)

def generate_doctor_sheet(output_path):
    """Generates the summary list for doctor's review"""
    c = canvas.Canvas(output_path, pagesize=landscape(A4))
    width, height = landscape(A4)
    
    c.setFont(FONT_NAME, 16)
    c.drawCentredString(width/2, height - 40, "リハビリテーション実施計画書：ドクター検討用リスト")
    
    # Headers
    c.setFont(FONT_NAME, 9)
    y = height - 80
    headers = ["患者名", "疾患名", "発症日", "目標", "治療方針", "（前回）ドクター所見", "今月変更点／記入欄"]
    x_offsets = [30, 100, 200, 280, 430, 580, 730]
    
    for i, h in enumerate(headers):
        c.drawString(x_offsets[i], y, h)
    
    c.line(20, y-5, width-20, y-5)
    y -= 25
    
    conn = get_connection()
    patients = conn.execute("SELECT id, name, disease_name, onset_date FROM patients WHERE status='入院中'").fetchall()
    
    for p in patients:
        plan = conn.execute("SELECT * FROM rehab_plans WHERE patient_id=? ORDER BY plan_date DESC LIMIT 1", (p["id"],)).fetchone()
        
        c.drawString(x_offsets[0], y, p["name"])
        c.drawString(x_offsets[1], y, (p["disease_name"] or "")[:15])
        c.drawString(x_offsets[2], y, str(p["onset_date"] or ""))
        
        if plan:
            c.drawString(x_offsets[3], y, (plan["goal_short"] or "")[:25])
            c.drawString(x_offsets[4], y, (plan["plan_pt"] or "")[:25])
            c.drawString(x_offsets[5], y, (plan["doctor_finding"] or "")[:20])
        
        c.line(20, y-20, width-20, y-20)
        y -= 40
        
        if y < 50:
            c.showPage()
            y = height - 50
    
    conn.close()
    c.save()
    print(f"Doctor Sheet generated at: {output_path}")

def generate_plan_21_pdf(patient_id, output_path):
    """Generates the official 2-page duplex-ready PDF for Form 21"""
    c = canvas.Canvas(output_path, pagesize=A4)
    # Page 1 logic ...
    # Placeholder for Page 1 replication logic
    c.setFont(FONT_NAME, 14)
    c.drawCentredString(297, 780, "リハビリテーション総合実施計画書 (Page 1)")
    c.showPage()
    
    # Page 2 logic ...
    c.drawCentredString(297, 780, "リハビリテーション総合実施計画書 (Page 2)")
    c.showPage()
    
    c.save()
    print(f"Form 21 PDF generated at: {output_path}")
