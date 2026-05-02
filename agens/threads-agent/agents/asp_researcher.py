"""
ASP Researcher Agent（楽天アフィリエイト版）
- 楽天アフィリエイトの商品をジャンルキーワードで検索
- 商品名・価格・カテゴリを取得
- おすすめ順にランキングして data/asp_recommendations.json に保存
- 人間は結果を見てリンクを楽天アフィリエイトで取得するだけ
"""
import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


class ASPResearcherAgent:
    def __init__(self, config, knowledge_dir, data_dir):
        self.config = config
        self.knowledge_dir = Path(knowledge_dir)
        self.data_dir = Path(data_dir)
        self.rakuten_app_id = os.environ.get("RAKUTEN_APP_ID", "")

    def _load_json(self, path, default):
        path = Path(path)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return default

    def _save_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_niche(self):
        profile = self._load_json(self.knowledge_dir / "account_profile.json", {})
        return profile.get("niche", "AI")

    def _search_rakuten(self, keyword, max_results=20):
        """楽天商品検索APIで商品を取得"""
        if not self.rakuten_app_id:
            logger.warning("ASPResearcher: RAKUTEN_APP_ID が未設定。モックデータを使用。")
            return []

        results = []
        try:
            url = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706"
            params = {
                "applicationId": self.rakuten_app_id,
                "keyword": keyword,
                "hits": min(max_results, 30),
                "sort": "-reviewCount",  # レビュー数順
                "formatVersion": 2,
            }
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            data = resp.json()

            for item in data.get("Items", [])[:max_results]:
                results.append({
                    "name": item.get("itemName", "")[:50],
                    "price": f"{item.get('itemPrice', 0):,}円",
                    "review_count": item.get("reviewCount", 0),
                    "review_average": item.get("reviewAverage", 0),
                    "item_url": item.get("itemUrl", ""),
                    "affiliate_url": "[楽天アフィリエイトで取得]",
                    "source": "楽天市場",
                    "keyword": keyword,
                })

        except Exception as e:
            logger.warning(f"ASPResearcher: 楽天API失敗: {e}")

        return results

    def _get_mock_results(self, niche):
        """APIキーなし・取得失敗時のモックデータ"""
        mock_data = {
            "AI": [
                {"name": "Claude Pro サブスク", "price": "月額約3,000円", "commission_type": "サブスク契約", "affiliate_url": "[楽天アフィリエイトで取得]", "note": "Anthropic公式（楽天経由なし）→直接アフィリ検討", "source": "mock"},
                {"name": "Anker PowerConf S500（AI搭載スピーカーフォン）", "price": "約20,000円", "commission_type": "購入", "affiliate_url": "[楽天アフィリエイトで取得]", "source": "mock"},
                {"name": "PLAUD NOTE AIボイスレコーダー", "price": "約30,000円", "commission_type": "購入", "affiliate_url": "[楽天アフィリエイトで取得]", "source": "mock"},
                {"name": "iPad（スマホAI活用向け）", "price": "約60,000円〜", "commission_type": "購入", "affiliate_url": "[楽天アフィリエイトで取得]", "source": "mock"},
                {"name": "Apple Pencil", "price": "約10,000円〜", "commission_type": "購入", "affiliate_url": "[楽天アフィリエイトで取得]", "source": "mock"},
            ],
            "ビジネス": [
                {"name": "ロジクール MX Keys キーボード", "price": "約15,000円", "commission_type": "購入", "affiliate_url": "[楽天アフィリエイトで取得]", "source": "mock"},
                {"name": "モバイルバッテリー Anker", "price": "約3,000〜8,000円", "commission_type": "購入", "affiliate_url": "[楽天アフィリエイトで取得]", "source": "mock"},
            ],
        }
        return mock_data.get(niche, mock_data.get("AI", []))

    def run(self, niche=None):
        """
        メイン実行。
        楽天アフィリエイトで紹介できる商品を収集してJSON保存。
        """
        if niche is None:
            niche = self._get_niche()

        logger.info(f"ASPResearcher: ジャンル「{niche}」の楽天商品をリサーチ中...")

        results = self._search_rakuten(niche)

        if not results:
            logger.warning("ASPResearcher: 楽天API取得失敗。モックデータを使用。")
            results = self._get_mock_results(niche)

        output = {
            "niche": niche,
            "researched_at": datetime.now().isoformat(),
            "total": len(results),
            "source": "楽天アフィリエイト",
            "note": "affiliate_urlが[楽天アフィリエイトで取得]の場合は https://affiliate.rakuten.co.jp/ で商品を検索してリンクを取得してください",
            "programs": results,
        }

        self._save_json(self.data_dir / "asp_recommendations.json", output)

        print(f"\n{'='*60}")
        print(f"  楽天アフィリエイト リサーチ結果 - ジャンル: {niche}")
        print(f"{'='*60}")
        for i, p in enumerate(results, 1):
            name = p.get("name", "")[:30]
            price = p.get("price", "不明")
            print(f"  {i}. {name} — {price}")

        print(f"\n  保存先: data/asp_recommendations.json")
        print(f"\n  次のステップ:")
        print(f"  1. 紹介したい商品を選ぶ")
        print(f"  2. https://affiliate.rakuten.co.jp/ でリンクを取得")
        print(f"  3. knowledge/account_profile.json の affiliate_links に追加")
        print(f"     例: {{\"商品キー\": \"https://hb.afl.rakuten.co.jp/...\"}}")
        print(f"{'='*60}\n")

        return results
