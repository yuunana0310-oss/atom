import os
import glob

def main():
    base = r"c:\Users\yuuna\agens"
    os.chdir(base)
    
    # 部門ごとのマッピング
    departments = {
        "00_general": {
            "guidelines": ["01_general_workflow.md"],
            "agents": [], "templates": [], "commands": []
        },
        "01_rehab_karte": {
            "agents": ["rehab_pm.md", "rehab_system_engineer.md", "rehab_ux_designer.md"],
            "commands": ["rehab_karte.md"],
            "guidelines": [], "templates": []
        },
        "02_medical_rehab": {
            "agents": ["medical_writer.md", "academic_researcher.md"],
            "commands": ["medical.md"],
            "guidelines": ["07_medical_writing.md"],
            "templates": ["clinical_document_template.md", "academic_presentation_template.md"]
        },
        "03_engineering": {
            "agents": ["lead_engineer.md", "qa_tester.md"],
            "commands": ["engineering.md"],
            "guidelines": ["04_coding_standards.md", "05_testing_and_qa.md"],
            "templates": ["tech_spec_template.md", "qa_report_template.md"]
        },
        "04_sns_marketing": {
            "agents": ["sns_manager.md", "content_creator.md", "marketing_analyst.md"],
            "commands": ["marketing.md"],
            "guidelines": ["02_sns_operation.md", "03_content_writing.md"],
            "templates": ["sns_post_template.md", "article_template.md"]
        },
        "05_research_strategy": {
            "agents": ["ai_researcher.md", "business_planner.md"],
            "commands": ["research.md"],
            "guidelines": ["06_prompt_engineering.md"],
            "templates": []
        },
        "06_creative": {
            "agents": ["designer.md"],
            "commands": ["creative.md"],
            "guidelines": [], "templates": []
        }
    }

    # パスの置換マップ作成 (old_path_str -> new_path_str)
    # 例: "agents/rehab_pm.md" -> "departments/01_rehab_karte/agents/rehab_pm.md"
    rename_map = {}
    replace_map = {}

    for dep_name, categories in departments.items():
        for cat, files in categories.items():
            for f in files:
                if cat == "commands":
                    old_path = os.path.join(".claude", "commands", f)
                    old_str = f".claude/commands/{f}"
                else:
                    old_path = os.path.join(cat, f)
                    old_str = f"{cat}/{f}"
                
                new_path = os.path.join("departments", dep_name, cat, f)
                new_str = f"departments/{dep_name}/{cat}/{f}"
                
                rename_map[old_path] = new_path
                replace_map[old_str] = new_str

    # 実際のファイル移動
    for old_path, new_path in rename_map.items():
        if os.path.exists(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            os.rename(old_path, new_path)
            print(f"Moved: {old_path} -> {new_path}")

    # 残った空ディレクトリの削除試行
    for cat in ["agents", "guidelines", "templates", os.path.join(".claude", "commands")]:
        try:
            if os.path.exists(cat) and not os.listdir(cat):
                os.rmdir(cat)
                print(f"Removed empty directory: {cat}")
        except OSError:
            pass

    # すべての md ファイル内の参照文字列を置換
    md_files = glob.glob(os.path.join(base, "**", "*.md"), recursive=True)
    for md_file in md_files:
        try:
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content
            for old_str, new_str in replace_map.items():
                new_content = new_content.replace(old_str, new_str)
            
            if content != new_content:
                with open(md_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated references in: {md_file}")
        except Exception as e:
            print(f"Failed to update {md_file}: {e}")

if __name__ == "__main__":
    main()
