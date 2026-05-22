# skill-intake scripts

本ディレクトリの責務: `run-skill-intake-aggregator` および sibling skill `run-notion-intake-publish` から呼ばれる**決定論処理を担う Python 3 スクリプト集**。LLM 判断に依存せず、入力に対して常に同じ出力を返すロジックのみを置く（Script First 原則）。macOS 標準 `/usr/bin/python3` で動作し、外部 pip パッケージ不要。

**スクリプト数: 27 本** (Python 3 標準ライブラリのみ、外部 pip パッケージ禁止)。

## カテゴリ別一覧

### Keychain 系 (1 本)

| スクリプト | サマリ |
|---|---|
| `keychain_get_secret.py` | macOS Keychain から Notion トークンを取得する唯一の経路。exit 44 で未登録を表現。 |

### Notion 系 (7 本)

| スクリプト | サマリ |
|---|---|
| `notion_http.py` | Notion REST API v1 への薄い wrapper。Notion-Version / Authorization を1箇所に閉じ込める。 |
| `create_notion_database.py` | `--mode=create|sync` で DB を作成または既存 DB を期待スキーマへ寄せる。 |
| `verify_notion_schema.py` | 期待スキーマと現状 DB を突き合わせ、過不足を `eval-log/notion-conflicts.json` に出力。 |
| `prepare_notion_assets.py` | `visuals/` を走査し SHA-256 付き `notion-manifest.json` を生成。 |
| `verify_notion_assets.py` | PNG 欠損・空ファイル・hash 不一致を MUST ゲート検証 (All-or-Nothing)。 |
| `render_notion_page.py` | `intake.json` から Notion ブロック JSON (`notion-blocks.json`) を組み立てる。 |
| `publish_notion_page.py` | Notion REST `POST /v1/pages` を実発火し、URL を返す。 |

### 品質ゲート系 (8 本)

| スクリプト | サマリ |
|---|---|
| `validate_intake.py` | intake.json のスキーマ検証 (`handoff-contract.md` 準拠)。 |
| `check_completeness.py` | 5 軸 (出力先・情報源・共有相手・真の課題・ナレッジ資産) 充足判定。 |
| `cross_check.py` | intake.md と intake.json の整合検証。 |
| `detect_contradictions.py` | SubAgent 出力間の矛盾検出。 |
| `extract_open_questions.py` | 未解決質問の抽出。 |
| `quality_gate.py` | 5 次元ルブリック自己採点 PASS/FAIL 判定。 |
| `measure_value_realized.py` | 真の課題言語化スコア (0-100) 採点。 |
| `render-intake-final.py` | intake-final-context.json から §0〜§11 完全版 Markdown を生成 (Jinja2 + JSON Schema 検証)。 |

### 図解系 (8 本)

| スクリプト | サマリ |
|---|---|
| `select_diagram_type.py` | セクション種別から最適な図解タイプを選択。 |
| `select_diagrams_per_section.py` | セクションごとの図解配置を 1〜3 図で決定。 |
| `compose_diagram.py` | Mermaid / SVG 構文を生成 (テンプレ展開)。 |
| `validate_mermaid.py` | Mermaid 構文検証 (失敗時は再生成を最大 2 回試行)。 |
| `enforce_visualization_rules.py` | 非エンジニア対応マスト 8 ルール強制。 |
| `optimize_layout.py` | 図解レイアウト最適化 (ノード配置調整)。 |
| `render_to_svg.py` | Mermaid → SVG 変換。 |
| `render_to_image.py` | SVG → PNG 化 (Notion は SVG ネイティブ表示不可)。 |

### intake 構築系 (2 本)

| スクリプト | サマリ |
|---|---|
| `convert_md_to_json.py` | intake.md から intake.json への derive 検証。 |
| `render_notion_page.py` | intake-final-context.json から Notion properties + children を投影 (v2)。 |

### self-update 系 (1 本)

| スクリプト | サマリ |
|---|---|
| `update_question_bank.py` | question-bank.md にパッチ適用 (`--apply` / `--rollback <hint>`)。 |

## 依存

- **Python 3 標準ライブラリのみ** (macOS 標準 `/usr/bin/python3`、3.9 以上)
- **外部 pip パッケージ禁止** (`requirements.txt` / `pyproject.toml` を本ディレクトリに置かない)
- 認証情報は必ず `keychain_get_secret.py` 経由で取得。環境変数・`.env`・コミット履歴に平文を残さない。
