# 🏥 リハカルテ製作部 コマンドルーター (/rehab_karte)

## 概要
ユーザーの最重要プロジェクトである「リハビリ特化型電子カルテ」の企画・設計・開発を行う際にロードします。

## 所属エージェントと得意領域
- **`departments/01_rehab_karte/agents/rehab_pm.md`**: カルテ業務の要件定義、機能の取捨選択、プロジェクト現場視点での評価
- **`departments/01_rehab_karte/agents/rehab_system_engineer.md`**: システムのバックエンド設計、データベース構築、セキュリティ実装
- **`departments/01_rehab_karte/agents/rehab_ux_designer.md`**: 臨床現場での圧倒的な使いやすさを追求したUI/UX設計・フロントエンド

## 起動ルール（司令塔向け）
1. リハカルテに関する開発・相談を受けた場合、まず `rehab_pm` に臨床現場の視点での仕様やアプローチを作らせてください。
2. 仕様が固まったら、画面の動作やレイアウトは `rehab_ux_designer` に、データ保存やAPI、セキュリティの裏側は `rehab_system_engineer` に設計・実装させてください。完成物は必ず `qa_tester` (Engineering部のもの)にレビュー依頼を出させて安全を担保させてください。
