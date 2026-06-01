# -*- coding: utf-8 -*-
"""
リハビリ患者管理表.xlsm を生成するスクリプト（Excel COM自動化）。
- 入力フォーム（氏名・入院日・発症日・リハ種別・主治医）
- 算定期限を自動計算（「○日目」= 起算日+（日数-1）の正しい数え方）
- 「台帳に登録」ボタン → VBAで台帳シートへ1行追記＋入力欄クリア
再実行で上書き再生成します。
"""
import os
import sys
import win32com.client as win32

OUT = r"C:\Users\yuuna\agens\リハ算定2026\リハビリ患者管理表.xlsm"

VBA_CODE = '''Option Explicit

Sub データ登録()
    Dim ws As Worksheet, db As Worksheet
    Set ws = ThisWorkbook.Sheets("入力")
    Set db = ThisWorkbook.Sheets("台帳")

    ' --- 必須チェック ---
    If Trim(CStr(ws.Range("C4").Value)) = "" Then
        MsgBox "「氏名」を入力してください。", vbExclamation, "入力チェック"
        ws.Range("C4").Select
        Exit Sub
    End If
    If Not IsDate(ws.Range("C5").Value) Then
        MsgBox "「入院日」を日付で入力してください（例 2026/6/1）。", vbExclamation, "入力チェック"
        ws.Range("C5").Select
        Exit Sub
    End If
    If Not IsDate(ws.Range("C6").Value) Then
        If MsgBox("「発症日」が未入力です。" & vbCrLf & _
                  "急性期リハ・休日リハ・標準算定日数の期限は空欄で登録されます。" & vbCrLf & _
                  "このまま登録しますか？", vbQuestion + vbYesNo, "確認") = vbNo Then
            ws.Range("C6").Select
            Exit Sub
        End If
    End If

    ' --- 次の空行 ---
    Dim r As Long
    r = db.Cells(db.Rows.Count, 2).End(xlUp).Row + 1
    If r < 2 Then r = 2

    ' --- 転記（計算結果は値で保存）---
    db.Cells(r, 1).Value = r - 1
    db.Cells(r, 2).Value = ws.Range("C4").Value
    db.Cells(r, 3).Value = ws.Range("C5").Value
    db.Cells(r, 4).Value = ws.Range("C6").Value
    db.Cells(r, 5).Value = ws.Range("C7").Value
    db.Cells(r, 6).Value = ws.Range("C8").Value
    db.Cells(r, 7).Value = ws.Range("F5").Value
    db.Cells(r, 8).Value = ws.Range("F6").Value
    db.Cells(r, 9).Value = ws.Range("F7").Value
    db.Cells(r, 10).Value = ws.Range("F8").Value
    db.Cells(r, 11).Value = ws.Range("F9").Value
    db.Cells(r, 12).Value = Now

    ' --- 書式 ---
    db.Range(db.Cells(r, 3), db.Cells(r, 11)).NumberFormat = "yyyy/mm/dd"
    db.Cells(r, 12).NumberFormat = "yyyy/mm/dd hh:mm"
    db.Range(db.Cells(r, 1), db.Cells(r, 12)).Borders.LineStyle = xlContinuous

    ' --- 入力欄クリア ---
    ws.Range("C4:C8").ClearContents
    ws.Range("C4").Select

    MsgBox "台帳に登録しました（" & (r - 1) & " 件目）。", vbInformation, "完了"
End Sub
'''


def main():
    if os.path.exists(OUT):
        try:
            os.remove(OUT)
        except Exception as e:
            print("既存ファイルを削除できません（開いている可能性）:", e)
            sys.exit(1)

    xl = win32.DispatchEx("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False
    try:
        wb = xl.Workbooks.Add()
        # 既定シートを使い回し、3枚に
        while wb.Sheets.Count < 3:
            wb.Sheets.Add(After=wb.Sheets(wb.Sheets.Count))
        ws = wb.Sheets(1); ws.Name = "入力"
        db = wb.Sheets(2); db.Name = "台帳"
        ms = wb.Sheets(3); ms.Name = "マスタ"

        # ===== マスタ =====
        ms.Range("A1").Value = "リハ種別"
        ms.Range("B1").Value = "標準算定日数"
        data = [("運動器Ⅰ", 150), ("脳血管Ⅱ", 180), ("呼吸器１", 90)]
        for i, (k, v) in enumerate(data):
            ms.Cells(2 + i, 1).Value = k
            ms.Cells(2 + i, 2).Value = v
        ms.Range("D1").Value = "主治医リスト（←ここを自院の医師名に編集してください）"
        for i, name in enumerate(["（例）山田 太郎", "（例）佐藤 花子", "（例）鈴木 一郎"]):
            ms.Cells(2 + i, 4).Value = name
        ms.Range("A1:B1").Font.Bold = True
        ms.Range("D1").Font.Bold = True
        ms.Columns("A:B").ColumnWidth = 14
        ms.Columns("D").ColumnWidth = 24

        # ===== 入力フォーム =====
        ws.Range("B1").Value = "リハビリ患者管理表（令和8年度算定対応）"
        ws.Range("B1").Font.Size = 16
        ws.Range("B1").Font.Bold = True
        ws.Range("B2").Value = "①患者情報を入力 →  ②「台帳に登録」ボタンをクリック"
        ws.Range("B2").Font.ColorIndex = 16

        labels = {"B4": "氏名", "B5": "入院日", "B6": "発症日",
                  "B7": "リハ種別", "B8": "主治医"}
        for cell, text in labels.items():
            ws.Range(cell).Value = text
            ws.Range(cell).Font.Bold = True
        ws.Range("C5").NumberFormat = "yyyy/mm/dd"
        ws.Range("C6").NumberFormat = "yyyy/mm/dd"

        # 入力セルの枠と色
        in_rng = ws.Range("C4:C8")
        in_rng.Borders.LineStyle = 1
        in_rng.Interior.ColorIndex = 19  # 薄い黄
        ws.Range("C5").Value = ""  # 空

        # ドロップダウン（リハ種別）
        v1 = ws.Range("C7").Validation
        v1.Delete()
        v1.Add(Type=3, AlertStyle=1, Operator=1, Formula1="=マスタ!$A$2:$A$4")
        # ドロップダウン（主治医）
        v2 = ws.Range("C8").Validation
        v2.Delete()
        v2.Add(Type=3, AlertStyle=1, Operator=1, Formula1="=マスタ!$D$2:$D$50")

        # 計算ラベル＆数式
        calc = {
            "E5": "早期リハ60点 最終日（入院3日目）", "F5": "=IF(C5=\"\",\"\",C5+2)",
            "E6": "早期リハ加算 最終日（入院14日目）", "F6": "=IF(C5=\"\",\"\",C5+13)",
            "E7": "急性期リハ加算 最終日（発症14日目）", "F7": "=IF(C6=\"\",\"\",C6+13)",
            "E8": "休日リハ加算 最終日（発症30日目）", "F8": "=IF(C6=\"\",\"\",C6+29)",
            "E9": "標準算定日数 最終日（種別別）", "F9": "=IF(OR(C6=\"\",C7=\"\"),\"\",C6+VLOOKUP(C7,マスタ!$A$2:$B$4,2,FALSE)-1)",
        }
        for cell, val in calc.items():
            if cell.startswith("E"):
                ws.Range(cell).Value = val
                ws.Range(cell).Font.ColorIndex = 5
            else:
                ws.Range(cell).Formula = val
                ws.Range(cell).NumberFormat = "yyyy/mm/dd"
                ws.Range(cell).Font.Bold = True

        # 注意書き
        ws.Range("E11").Value = "※「○日目」は起算日を1日目として数えます（＋日数−1）。手計算のズレ防止のため自動化。"
        ws.Range("E12").Value = "※ 早期リハの起算日＝入院日／急性期・休日リハの起算日＝発症日。"
        ws.Range("E13").Value = "※ 主治医の選択肢は「マスタ」シートのD列で編集できます。"
        for c in ("E11", "E12", "E13"):
            ws.Range(c).Font.Size = 9
            ws.Range(c).Font.ColorIndex = 16

        ws.Columns("B").ColumnWidth = 4
        ws.Columns("C").ColumnWidth = 16
        ws.Columns("D").ColumnWidth = 2
        ws.Columns("E").ColumnWidth = 34
        ws.Columns("F").ColumnWidth = 16

        # ボタン（フォームコントロール）
        btn = ws.Buttons().Add(ws.Range("B10").Left, ws.Range("B10").Top + 4, 200, 44)
        btn.OnAction = "データ登録"
        btn.Characters.Text = "▶ 台帳に登録"
        try:
            btn.Font.Size = 13
            btn.Font.Bold = True
        except Exception:
            pass

        # ===== 台帳 =====
        headers = ["No", "氏名", "入院日", "発症日", "リハ種別", "主治医",
                   "早期リハ60点 最終日(入院3日目)", "早期リハ加算 最終日(入院14日目)",
                   "急性期リハ加算 最終日(発症14日目)", "休日リハ加算 最終日(発症30日目)",
                   "標準算定日数 最終日", "登録日時"]
        for i, h in enumerate(headers):
            db.Cells(1, 1 + i).Value = h
        hr = db.Range(db.Cells(1, 1), db.Cells(1, len(headers)))
        hr.Font.Bold = True
        hr.Interior.ColorIndex = 37  # 薄い青
        hr.Borders.LineStyle = 1
        db.Rows(1).RowHeight = 30
        hr.WrapText = True
        db.Columns("A").ColumnWidth = 5
        db.Columns("B").ColumnWidth = 14
        for col in ("C", "D", "E", "F"):
            db.Columns(col).ColumnWidth = 12
        for col in ("G", "H", "I", "J", "K"):
            db.Columns(col).ColumnWidth = 16
        db.Columns("L").ColumnWidth = 18
        db.Application.ActiveWindow.SplitRow = 1
        db.Application.ActiveWindow.FreezePanes = True

        # VBAコード挿入
        mod = wb.VBProject.VBComponents.Add(1)  # 1 = 標準モジュール
        mod.Name = "登録処理"
        mod.CodeModule.AddFromString(VBA_CODE)

        ws.Activate()
        ws.Range("C4").Select()

        # 保存（52 = xlOpenXMLWorkbookMacroEnabled .xlsm）
        wb.SaveAs(OUT, FileFormat=52)
        wb.Close(SaveChanges=False)
        print("OK:", OUT)
    finally:
        xl.Quit()


if __name__ == "__main__":
    main()
