import openpyxl
import os

path = r"C:\Users\yuuna\Desktop\e21 (1).xlsx"

def dump_excel(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    print(f"Sheet Name: {ws.title}")
    
    # Dump 60x20 area to see the layout
    for r in range(1, 61):
        row_values = []
        for c in range(1, 21):
            val = ws.cell(r, c).value
            if val is None:
                row_values.append("")
            else:
                row_values.append(str(val))
        print(f"R{r:02d}: " + " | ".join(row_values))

if __name__ == "__main__":
    dump_excel(path)
