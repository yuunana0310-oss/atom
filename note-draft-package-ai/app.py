"""note 画像付き下書きパッケージ生成アプリ（Streamlit）。

起動:
    streamlit run app.py
"""
from __future__ import annotations

import os
import traceback
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src import (
    article_planner,
    article_writer,
    image_generator,
    image_prompt_generator,
    package_writer,
    utils,
)

load_dotenv()

ROOT = Path(__file__).resolve().parent
OUTPUT_ROOT = os.getenv("OUTPUT_DIR", "outputs")
PRODUCTS = utils.load_json(ROOT / "data" / "products.json") or []

st.set_page_config(page_title="note 画像付き下書きパッケージ生成", layout="wide")
st.title("note 画像付き下書きパッケージ生成")
st.caption("OpenAI APIで記事本文・画像・貼り付けテキストをまとめて生成します。noteへの直接投稿は行いません。")

# ---------------- 入力フォーム ----------------
with st.form("inputs"):
    col1, col2 = st.columns(2)
    with col1:
        theme = st.text_input("記事テーマ *", placeholder="例）医療職の資料作成はAIでどう変わるか")
        target = st.text_input("ターゲット *", value="医療職、理学療法士、介護職、AI初心者")
        article_type = st.selectbox(
            "記事タイプ",
            ["販売導線型", "共感ストーリー型", "ノウハウ型", "問題提起型", "実績報告型", "海外展開型", "商品説明型"],
        )
        purpose = st.selectbox(
            "記事の目的",
            [
                "note購入につなげる",
                "Threadsから流入させる",
                "プロフィール導線に使う",
                "無料記事として信頼形成する",
                "有料記事の導入にする",
            ],
        )
        tone = st.selectbox(
            "文体",
            ["あとむさん口調", "医療職向け丁寧", "note販売ページ風", "共感強め", "論理強め", "海外向け英語"],
        )

    with col2:
        product_options = ["（指定しない）"] + [p["name"] for p in PRODUCTS] + ["（手入力）"]
        product_select = st.selectbox("売りたい商品", product_options)
        product_name = ""
        product_description = ""
        product_cta = ""
        if product_select == "（手入力）":
            product_name = st.text_input("商品名（手入力）")
            product_description = st.text_area("商品説明（手入力）", height=80)
            product_cta = st.text_input("CTA文（任意）")
        elif product_select != "（指定しない）":
            chosen = next((p for p in PRODUCTS if p["name"] == product_select), None)
            if chosen:
                product_name = chosen["name"]
                product_description = chosen.get("description", "")
                product_cta = chosen.get("cta", "")
                st.caption(product_description)

        body_image_count = st.slider("本文画像枚数", 0, 4, 2)
        image_taste = st.selectbox(
            "画像テイスト",
            [
                "医療エディトリアル",
                "高密度インフォグラフィック",
                "ダークでムーディー",
                "クリーン医療図解",
                "Clinical Visual System風",
            ],
        )
        quality = st.checkbox("勝負記事モード（QUALITY_MODELを使用）", value=False)
        skip_images = st.checkbox("画像生成をスキップ（テキストのみ）", value=False)

    submitted = st.form_submit_button("パッケージを生成する", type="primary")


# ---------------- 実行 ----------------
if submitted:
    if not theme.strip():
        st.error("記事テーマを入力してください")
        st.stop()
    if not os.getenv("OPENAI_API_KEY"):
        st.error(".env に OPENAI_API_KEY を設定してください")
        st.stop()

    inputs = {
        "theme": theme,
        "target": target,
        "article_type": article_type,
        "purpose": purpose,
        "tone": tone,
        "product_name": product_name or None,
        "product_description": product_description or None,
        "body_image_count": body_image_count,
        "image_taste": image_taste,
        "quality": quality,
        "skip_images": skip_images,
    }

    progress = st.progress(0, text="記事設計中...")

    try:
        # STEP 0: 出力ディレクトリ確保
        out_dir = utils.make_output_dir(ROOT / OUTPUT_ROOT, theme)

        # STEP 1: 記事設計
        plan = article_planner.plan_article(
            theme=theme,
            target=target,
            article_type=article_type,
            purpose=purpose,
            tone=tone,
            body_image_count=body_image_count,
            product_name=product_name or None,
            product_description=product_description or None,
            quality=quality,
        )
        progress.progress(25, text="本文を執筆中...")

        # STEP 2: 本文生成
        article = article_writer.write_article(
            plan=plan,
            theme=theme,
            target=target,
            article_type=article_type,
            purpose=purpose,
            tone=tone,
            product_name=product_name or None,
            product_description=product_description or None,
            product_cta=product_cta or None,
            quality=quality,
        )
        progress.progress(55, text="画像プロンプトを生成中...")

        # STEP 3+4+5: 画像
        image_prompts: dict = {}
        saved_images: dict = {}
        image_errors: list = []
        if not skip_images and body_image_count + 1 > 0:
            image_prompts = image_prompt_generator.generate_prompts(
                plan=plan,
                theme=theme,
                image_taste=image_taste,
                body_image_count=body_image_count,
                quality=quality,
            )
            progress.progress(70, text="画像を生成中...（時間がかかります）")
            saved_images, image_errors = image_generator.generate_all_images(
                prompts=image_prompts,
                images_dir=out_dir / "images",
            )

        progress.progress(90, text="パッケージ保存中...")

        result_dir = package_writer.write_package(
            out_dir=out_dir,
            inputs=inputs,
            plan=plan,
            article=article,
            image_prompts=image_prompts,
            saved_images=saved_images,
            image_errors=image_errors,
        )

        progress.progress(100, text="完了")
        st.success(f"パッケージを保存しました: {result_dir}")

        # ---------------- プレビュー ----------------
        st.subheader("タイトル")
        st.write(article.get("title", ""))
        with st.expander("タイトル候補一覧"):
            for t in plan.get("title_candidates", []):
                st.write(f"- {t}")

        st.subheader("リード文")
        st.write(article.get("lead", ""))

        st.subheader("本文プレビュー（Markdown）")
        st.markdown(article.get("body_markdown", ""))

        if saved_images:
            st.subheader("生成画像")
            cols = st.columns(min(len(saved_images), 3))
            for i, (role, path) in enumerate(saved_images.items()):
                with cols[i % len(cols)]:
                    st.image(str(path), caption=role)

        if image_errors:
            st.warning("一部の画像生成に失敗しました：")
            for e in image_errors:
                st.write(f"- {e}")

        with st.expander("plan.json"):
            st.json(plan)

    except Exception as e:  # noqa: BLE001
        st.error(f"エラー: {type(e).__name__}: {e}")
        st.code(traceback.format_exc())
