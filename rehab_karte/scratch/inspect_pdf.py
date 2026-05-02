import pdfplumber
import csv
import os

pdf_path = r"C:\Users\yuuna\Desktop\b21 (1).pdf"
output_info = "pdf_structure_dump.txt"

with open(output_info, "w", encoding="utf-8") as f:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                f.write(f"--- PAGE {i+1} ---\n")
                # Text extraction
                text = page.extract_text()
                f.write("TEXT:\n")
                f.write(str(text) + "\n\n")
                
                # Table extraction
                f.write("TABLES:\n")
                tables = page.extract_tables()
                for j, table in enumerate(tables):
                    f.write(f"Table {j}:\n")
                    for row in table:
                        f.write(str(row) + "\n")
                    f.write("\n")
        print(f"Extraction complete. Results saved to {output_info}")
    except Exception as e:
        print(f"Error: {e}")
