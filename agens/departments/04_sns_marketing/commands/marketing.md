# 📈 SNS・マーケティング部 コマンドルーター (/marketing)

## 概要
SNS運用、記事執筆、マーケティングデータ分析、コンテンツ戦略に関する業務が発生した際にロードします。

## 所属エージェントと得意領域
- **`departments/04_sns_marketing/agents/rehab_pr_manager.md`**: リハカルテ開発過程の専属広報、プロセスエコノミー的発信、開発裏話のアピール
- **`departments/04_sns_marketing/agents/sns_manager.md`**: SNS発信戦略、コミュニティ運用、投稿ドラフトの作成（Threads/Twitter等）
- **`departments/04_sns_marketing/agents/content_creator.md`**: noteやブログ向け長文記事の執筆
- **`departments/04_sns_marketing/agents/marketing_analyst.md`**: ターゲット層・キーワード分析、テーマツリー(`theme_tree.json`)構築とデータ提供

## 起動ルール（司令塔向け）
1. 「今週のnote記事を書いて」という依頼の場合、まず `marketing_analyst` にトレンドキーワードのリストアップをさせ、次に `content_creator` へ執筆させ、最後に `sns_manager` へ告知文を作成させてください。
2. 提供された「既存のスキルや知見」をSNSで広める場合は、この部門を積極的に活用してください。
