import openpyxl
import os

path = r"C:\Users\yuuna\Desktop\e21 (1).xlsx"

def exhaustive_dump(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active
    print(f"--- FULL SHEET DUMP: {ws.title} ---")
    
    # Dump 120x30 to be safe
    for r in range(1, 121):
        row_vals = []
        for c in range(1, 31):
            val = ws.cell(r, c).value
            if val is None:
                row_vals.append("")
            else:
                row_vals.append(str(val).replace("\n", " "))
        
        # Only print rows that have at least one value
        row_str = " | ".join(row_vals)
        if row_str.replace("|", "").strip():
            print(f"R{r:03d}: {row_str}")

if __name__ == "__main__":
    exhaustive_dump(path)
