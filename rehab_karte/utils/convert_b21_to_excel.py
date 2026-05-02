import pdfplumber
import xlsxwriter
import os
import math

def convert_pdf_to_excel_final(pdf_path, output_path):
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found at {pdf_path}")
        return

    # Constants
    GRID_UNIT = 5.0  # Points per cell
    
    # Initialize Excel workbook
    workbook = xlsxwriter.Workbook(output_path)
    
    # Define formats cache
    formats = {}
    def get_format(border_flags=0, bold=False, size=9, is_text=False):
        key = (border_flags, bold, size, is_text)
        if key not in formats:
            props = {
                'size': size, 
                'valign': 'vcenter', 
                'align': 'left'
            }
            if bold: props['bold'] = True
            if border_flags & 1: props['top'] = 1
            if border_flags & 2: props['bottom'] = 1
            if border_flags & 4: props['left'] = 1
            if border_flags & 8: props['right'] = 1
            
            # Use white background for text to clear the grid under it
            if is_text:
                props['bg_color'] = 'white'
                
            formats[key] = workbook.add_format(props)
        return formats[key]

    with pdfplumber.open(pdf_path) as pdf:
        for p_idx, page in enumerate(pdf.pages):
            sheet = workbook.add_worksheet(f"Page {p_idx + 1}")
            
            w, h = float(page.width), float(page.height)
            num_cols = math.ceil(w / GRID_UNIT)
            num_rows = math.ceil(h / GRID_UNIT)
            
            # Setup grid sizing
            for c in range(num_cols + 1):
                sheet.set_column(c, c, 5.0 / 7.2) 
            for r in range(num_rows + 1):
                sheet.set_row(r, 5.0 * 0.75) 

            # --- 1. PROCESS LINES FOR BORDERS ---
            grid_borders = [[0] * (num_cols + 1) for _ in range(num_rows + 1)]
            
            for l in page.lines:
                x0, y0, x1, y1 = float(l['x0']), float(l['top']), float(l['x1']), float(l['bottom'])
                if abs(y0 - y1) < 1.0: # Horizontal
                    row, c_start, c_end = round(y0/GRID_UNIT), round(x0/GRID_UNIT), round(x1/GRID_UNIT)
                    for c in range(c_start, c_end):
                        if 0 <= row < num_rows and 0 <= c < num_cols: grid_borders[row][c] |= 1
                if abs(x0 - x1) < 1.0: # Vertical
                    col, r_start, r_end = round(x0/GRID_UNIT), round(y0/GRID_UNIT), round(y1/GRID_UNIT)
                    for r in range(r_start, r_end):
                        if 0 <= r < num_rows and 0 <= col < num_cols: grid_borders[r][col] |= 4
            
            for rect in page.rects:
                x0, y0, x1, y1 = float(rect['x0']), float(rect['top']), float(rect['x1']), float(rect['bottom'])
                cs, ce, rs, re = round(x0/GRID_UNIT), round(x1/GRID_UNIT), round(y0/GRID_UNIT), round(y1/GRID_UNIT)
                for c in range(cs, ce):
                    if 0 <= rs < num_rows and 0 <= c < num_cols: grid_borders[rs][c] |= 1
                    if 0 <= re < num_rows and 0 <= c < num_cols: grid_borders[re][c] |= 1
                for r in range(rs, re):
                    if 0 <= r < num_rows and 0 <= cs < num_cols: grid_borders[r][cs] |= 4
                    if 0 <= r < num_rows and 0 <= ce < num_cols: grid_borders[r][ce] |= 4

            # Track merged cells to avoid collisions
            merged_cells = set()

            # --- 2. PROCESS TEXT WITH MERGING ---
            words = page.extract_words()
            for w_obj in words:
                text = w_obj['text']
                r, c = round(float(w_obj['top']) / GRID_UNIT), round(float(w_obj['x0']) / GRID_UNIT)
                span_cols = max(1, math.ceil(float(w_obj['width']) / GRID_UNIT))
                span_rows = max(1, math.ceil(float(w_obj['height']) / GRID_UNIT))
                
                if 0 <= r < num_rows and 0 <= c < num_cols:
                    is_bold = "Bold" in w_obj.get('fontname', '') or "Gothic" in w_obj.get('fontname', '')
                    size = max(8, round(float(w_obj.get('size', 9.0))))
                    b_flags = grid_borders[r][c]
                    
                    # Check if any cell in the range is already merged
                    collision = False
                    for mr in range(r, r + span_rows):
                        for mc in range(c, c + span_cols):
                            if (mr, mc) in merged_cells:
                                collision = True
                                break
                    
                    if not collision:
                        if span_cols > 1 or span_rows > 1:
                            sheet.merge_range(r, c, r + span_rows - 1, c + span_cols - 1, text, get_format(b_flags, is_bold, size, True))
                            for mr in range(r, r + span_rows):
                                for mc in range(c, c + span_cols):
                                    merged_cells.add((mr, mc))
                        else:
                            sheet.write(r, c, text, get_format(b_flags, is_bold, size, True))
                            merged_cells.add((r, c))

            # --- 3. APPLY REMAINING BORDERS ---
            for r in range(num_rows):
                for c in range(num_cols):
                    if (r, c) not in merged_cells and grid_borders[r][c] > 0:
                        sheet.write(r, c, "", get_format(border_flags=grid_borders[r][c]))

    workbook.close()
    print(f"Final Excel generated at: {output_path}")

if __name__ == "__main__":
    pdf_in = r"C:\Users\yuuna\Desktop\b21 (1).pdf"
    excel_out = r"C:\Users\yuuna\Desktop\様式21号_完成版(b21).xlsx"
    convert_pdf_to_excel_final(pdf_in, excel_out)
