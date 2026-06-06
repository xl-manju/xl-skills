# shared_state — elegant-review / skill-intake Notion出力 (Phase1俯瞰)

## 全体像（出力経路 起点→終点）
aggregator R11 or run-notion-intake-publish Step3 → intake_publish_pipeline.py:main → [render_notion_page→notion-blocks.json] → [quality_gate.gate] → [publish_notion_page.py:main] → notion_fetch(POST /pages | PATCH /pages/{id}) → result.json/url.txt

## 第一印象の懸念点(最大5)
1. parent が `{database_id}` 固定。`--page-id` 入口が無く「指定ページ」出力経路が存在しない（page vs DB の設計不一致＝根本）
2. update/create 分岐が `--result-out` ファイルの存在・健全性のみ依存。hint/intakeパス変動で別ページ量産
3. DB-ID解決は env(INTAKE_NOTION_DATABASE_ID) > config 優先＋`--database-id`任意。「指定したつもり」逸脱
4. check_db_match は`--database-id`渡した時だけ発火。通常起動で出力先一致が無検査
5. fail-open(require_or_skip allow_skip) と fail-closed(exit2) が経路混在 → publish skip→skill生成横流れ

## Phase2観測ポイント（単一経路がどこで分岐/逸脱するか）
A. parent種別固定(publish:281) / B. page_id単一情報源依存(158-173,287) / C. env追い越し(notion_config:87-89) / D. db_match条件付き(quality_gate:44,183) / E. fail-open/closed混在(notion_config:121-150)
