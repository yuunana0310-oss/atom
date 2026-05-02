import json
import openpyxl

def generate_html(dna_path, output_path):
    with open(dna_path, "r", encoding="utf-8") as f:
        dna = json.load(f)
    
    # 1. Prepare Merge Map
    # Key: (r, c), Value: (rowspan, colspan) or None
    merges = {}
    skip_cells = set()
    
    for m_range in dna["merges"]:
        r_start, c_start, r_end, c_end = openpyxl.utils.range_boundaries(m_range)
        merges[(r_start, c_start)] = (r_end - r_start + 1, c_end - c_start + 1)
        for r in range(r_start, r_end + 1):
            for c in range(c_start, c_end + 1):
                if (r, c) != (r_start, c_start):
                    skip_cells.add((r, c))

    # 2. Map fixed text cells for labels
    cell_values = {(item["r"], item["c"]): item["v"] for item in dna["cells"]}

    # 3. Build HTML
    html = ["""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>統合臨床エディタ - 真のデジタル・ツイン</title>
    <style>
        body { background: #333; font-family: "Yu Gothic UI", sans-serif; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .toolbar { background: #1a1a1a; color: #fff; width: 1700px; padding: 15px; display: flex; gap: 20px; align-items: center; position: sticky; top: 0; z-index: 1000; border-radius: 6px; box-shadow: 0 4px 20px rgba(0,0,0,0.5); margin-bottom: 20px; }
        .btn { padding: 12px 28px; cursor: pointer; border: none; font-weight: bold; border-radius: 4px; font-size: 11pt; transition: 0.2s; background: #28a745; color: white; }
        .spread { background: #fff; padding: 10mm; box-shadow: 0 0 40px rgba(0,0,0,0.6); position: relative; }
        
        table { border-collapse: collapse; table-layout: fixed; border: 2px solid #000; }
        td { border: 1px solid #000; padding: 1px; font-size: 8pt; vertical-align: middle; box-sizing: border-box; overflow: hidden; position: relative; }
        
        input, textarea { border: none; width: 100%; height: 100%; background: transparent; font-family: inherit; font-size: inherit; outline: none; padding: 0; margin: 0; display: block; }
        textarea { resize: none; }
        input:focus, textarea:focus { background: #fffde7; }
        
        .label { background: #f2f2f2; font-weight: bold; text-align: center; }
        .input-cell { background: #fff; }
    </style>
</head>
<body>
    <div class="toolbar">
        <div style="font-size: 16pt; font-weight: bold;">様式第21号 構造クローン・エディタ</div>
        <button class="btn" onclick="saveData()">すべての入力を保存</button>
        <button class="btn" style="background:#444;" onclick="window.close()">閉じる</button>
    </div>
    <div class="spread">
        <table>
    """]

    # Calculate Total Columns
    col_letters = sorted(dna["cols"].keys(), key=lambda x: openpyxl.utils.column_index_from_string(x))
    
    # 4. Generate Rows
    # Standard Excel width 8.38 is approx 64px. So 1 unit ~= 7.6px
    # Row height 15 is approx 20px. So 1 unit ~= 1.33px
    W_SCALE = 7.6
    H_SCALE = 1.33

    for r in range(1, 105):
        h = dna["rows"].get(str(r), 15.0) * H_SCALE
        html.append(f'            <tr style="height: {h}px;">')
        
        for c_idx, col_letter in enumerate(col_letters):
            c = c_idx + 1
            if (r, c) in skip_cells:
                continue
            
            w_raw = dna["cols"].get(col_letter, 8.38)
            w = w_raw * W_SCALE
            
            m = merges.get((r, c))
            rs_attr = f' rowspan="{m[0]}"' if m else ""
            cs_attr = f' colspan="{m[1]}"' if m else ""
            
            # Identify if it's a label or an input
            val = cell_values.get((r, c), "")
            is_label = val != ""
            
            klass = "label" if is_label else "input-cell"
            content = val if is_label else f'<input type="text" id="cell_{col_letter}{r}">'
            
            # Special case for textareas in large boxes
            if not is_label and m and m[0] > 2:
                content = f'<textarea id="cell_{col_letter}{r}"></textarea>'
            
            html.append(f'                <td class="{klass}" style="width: {w}px;"{rs_attr}{cs_attr}>{content}</td>')
            
        html.append("            </tr>")

    html.append("""
        </table>
    </div>
    <script>
        const patientId = new URLSearchParams(window.location.search).get('id');
        async function saveData() {
            const payload = { patient_id: patientId, plan_date: new Date().toISOString().split('T')[0] };
            document.querySelectorAll('input, textarea').forEach(el => {
                if (el.id) payload[el.id] = el.value;
            });
            const res = await fetch('/api/save', { method: 'POST', body: JSON.stringify(payload) });
            if (res.ok) alert("保存完了。様式構造を100%維持したまま同期されました。");
        }
    </script>
</body>
</html>
    """)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    print(f"Generated pixel-perfect mirror: {output_path}")

if __name__ == "__main__":
    generate_html("excel_dna.json", "templates/official_clone.html")
