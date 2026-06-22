# mf-kessai-invoice-check テスト戦略 (SSOT)

> このファイルが**唯一の真実 (Single Source of Truth)**。今どこまで出来ていて・次に何を
> すれば良いかは、ここだけ見れば分かる状態を保つ。作業のたびに**随時更新**する。
> サブエージェントもこのファイルを起点に文脈を得る。
>
> **鉄則**: 進捗は自己申告でなく**機械事実**で記す。PASS の根拠は「pytest の exit code = 0」
> 「`ls`/`git status` の実出力」のみ。テスト件数や「やった」は、実コマンド出力を
> `/tmp/*.txt` に書き Read して確認した結果だけを書く (Bash 末尾 stdout は壊れることがある)。

最終更新: 2026-06-22

---

## 0. このプラグインが保証したいこと (なぜテストするか)

MoneyForward 掛け払いの**請求書発行漏れ**を毎月検知し、結果を Notion DB に**顧客ID単位で
冪等に**蓄積する。壊れると「発行漏れの見逃し」または「Notion 履歴の重複/破壊」に直結する。
よって守るべき不変条件は次の 3 つ:

- **I1 (検知正当性)**: 前月発行・今月未発行 → 発行漏れ候補。金額変動 → 検知。誤検知しない。
- **I2 (冪等性)**: 同じ月を二度 sink しても Notion に行が重複しない。月が変わっても新規ページを
  作らず、顧客IDで既存ページを更新する。
- **I3 (移植性)**: 任意の install 先・本番環境で、手動セットアップ無しに動く (標準ライブラリのみ
  をランタイム依存とする)。

テストはこの I1/I2/I3 が**将来の変更で無言で壊れない**ことを保証するために存在する。

---

## 1. 現在のステータス (一目で分かる進捗表)

| Phase | 内容 | 状態 | 根拠 (機械事実) |
|---|---|---|---|
| P0 | 環境監査・dev 依存の導入 | ✅ 完了 | `requirements-dev.txt` 作成、6 パッケージ import OK (`/tmp/mfk_pipinstall.txt`) |
| P1 | 標準ローカルテスト基盤 | ✅ 完了 | `pytest.ini` (importlib+pythonpath)、sys.path 撤去、**41 passed / exit 0** をランダム順・並列・カバレッジで実証 (`/tmp/mfk_verify.txt`) |
| P2 | CI 配線 (再発防止の根本修正) | ✅ 完了 | `creator-kit-ci.yml` に per-plugin pytest ステップ追加。ローカルでループ実証 (`/tmp/mfk_ci_sim.txt`、found=1/exit 0/YAML_OK) |
| P3 | この SSOT ドキュメント | ✅ 完了 (随時更新) | 本ファイル |
| P4 | L3 real_test (実 Notion 往復) | ✅ 完了 | `tests/test_real_notion.py` 作成。secrets 無しで **2 skipped / exit 0**、既存 41 は緑を実証 (`/tmp/mfk_l3.txt`)。`MFK_TEST_DATABASE_ID` を持つ運用者環境でのみ実 API 往復 |
| P5 | 自己検証ループ (別 SubAgent レビュー) | ✅ 完了 (ADEQUATE) | §6。round1 R2=FAIL→3死角是正→**round2 で別contextが M3/M4 再ミューテーションし検出を確認、overall=ADEQUATE**。45 passed |
| P6 | deprecated 列の移行 | ✅ 完了 | schema に `deprecated_properties` 宣言。build が whitelist 削除 (現行列は不削除の安全制約)、verify が residual を FAIL 化。`tests/test_db_migration.py` 7本。ミューテーションで検出力実証 (`/tmp/mfk_p6_mutation.txt`) |

**次にやること (next action)**: 全フェーズ (P0–P6) 完了。**52 passed / 2 skipped / exit 0**。残るは
ブランチ作成→コミット→PR (push/PR は実行前に内容を提示して確認)。

---

## 2. テストの 3 層構造 (何を・どの層で守るか)

| 層 | 名前 | 対象 | ネットワーク | 速度 | 実体 |
|---|---|---|---|---|---|
| L1 | Unit | 純関数・ファイル操作 (diff 判定 / 出力先解決 / table 行構築) | 不要 | 即時 | `tests/test_invoice_diff.py`, `test_check_invoice_gaps.py`, `test_notion_invoice_sink.py` (fake store) |
| L2 | Contract | plugin manifest / schema / package 契約 | 不要 | 即時 | `tests/test_plugin_contract.py` |
| L3 | Real | 実 Notion DB への verify→upsert→read-back→再実行冪等 | 必要 | 数秒 | `tests/test_real_notion.py` (secrets 無しで skip)。§5 |

- L1/L2 は**毎 push で必ず緑**であるべき (API 不要なので CI で常時実行)。
- L3 は secrets があるときだけ走る (無ければ `pytest.mark.skip`)。本番同等の往復で I2 冪等性を
  実証する。mock では捕まえられない「実 API のレスポンス形・ページネーション・型」を守る。

カバレッジ実測 (`/tmp/mfk_verify.txt`): `notion_invoice_sink.py` 79% / `check_invoice_gaps.py` 55% /
`mfk_api.py` 18% / `mfk_keychain.py` 26%。**低い 2 つ (api/keychain) はネットワーク層**で、
L1 では原理的に届かない。ここは L3 real_test が担保すべき範囲だと数値が示している。

---

## 3. どう自動化したか (一個ずつ目視しない仕組み)

- **ローカル**: `cd plugins/mf-kessai-invoice-check && python3 -m pytest tests/ -q`。exit code が
  唯一の合否。pytest-randomly が毎回**実行順をランダム化**し順序依存バグを自動検出。
  `-n auto` (xdist) で並列、`--cov` で抜けを可視化。
- **CI** (`.github/workflows/creator-kit-ci.yml`): `plugins/*/tests` を**総当り**で pytest 実行。
  新規 plugin が `tests/` を足せば自動で CI 対象になり「配線忘れで無言腐敗」を構造的に封じる。
  dev 依存は `requirements-dev.txt` 一枚を SSOT として install。
- **再発防止の原理**: 「人間が一個ずつ叩いて目視」を、CI の exit code 門番に置換した。壊れた
  変更は PR の時点で赤くなり、マージできない。

---

## 4. 検証規律 (捏造を防ぐルール)

1. 合否は **exit code のみ**。「N passed」の見た目では判断しない。
2. Bash の末尾 stdout は壊れることがある → **結果は `/tmp/*.txt` に書き出し Read** して確認。
3. 「やった」は **`git status` / `ls` の実出力**で裏取りしてから書く。SubAgent の自己申告報告は
   `git diff` / exit code で二段確認する (形式パターン検出と実装意図は区別できない)。
4. 自作スクリプトで検証しない。**業界標準** (pytest, pytest-randomly, coverage) を使う。

---

## 5. L3 real_test (実装済み: `tests/test_real_notion.py`)

目的: mock では守れない「実 Notion API との契約」と「I2 冪等性の往復実証」を守る。

実装した手順 (サンドボックス DB に対して):
1. schema verify: サンドボックス DB に集約モデルの必須事実列が揃うことを実 API で確認。
2. 合成テスト行 (顧客ID=`__mfk_l3_test__<uuid>`, 対象年月=`2099-01`) を `upsert` → Notion を
   read-back し、顧客IDページ・本文 table の当月行・今月金額セルが期待通りか検証。
3. **同じ顧客・同じ月を金額だけ変えて再 upsert** → `created==0/updated==1` (新規ページを作らない)、
   ページが一意のまま、当月行が重複せず既存行が更新される (I2 冪等性) ことを実 API で確認。
4. 後始末: 作成した顧客ページを `archived=True` で必ずアーカイブ (finally)。

安全弁: 専用サンドボックス DB を環境変数 `MFK_TEST_DATABASE_ID` で受け取る。未設定なら
`pytest.skip` (本番 DB は決して使わない)。`NOTION_API_KEY`/Keychain が引けなくても skip。
→ secrets を持つ運用者環境でのみ実行され、CI / 一般環境では無言で skip する
(実証: `41 passed, 2 skipped, exit 0` / `/tmp/mfk_l3.txt`)。

---

## 6. 自己検証ループ (別 SubAgent によるレビュー)

proposer ≠ approver の原則 (テストを書いた本人が「十分」と自己承認しない)。独立 context の
レビュア SubAgent に次を判定させる:

- **R1 (機械事実)**: 主張する pytest 結果は実際に再現するか (exit 0 / 件数)。
- **R2 (妥当性)**: テストは I1/I2/I3 を実際に守っているか。アサーションが緩く偽 PASS していないか。
- **R3 (検出力)**: 故意にロジックを壊したらテストが落ちるか (ミューテーション的観点)。

判定が「不足」なら指摘を是正し、再レビュー (最大 3 周)。「十分」なら完了。結果は本 §1 表に反映。

### レビュー履歴

**round 1 — overall: INADEQUATE (R1 PASS / R3 PASS / R2 FAIL)**

独立レビュアが 4 ミューテーションを /tmp 複製で実施し、I2 冪等性の**死角を実証**した:

| ミューテーション | 結果 (round1) | 意味 |
|---|---|---|
| `detect_gaps` の差集合反転 | 4 failed (検出) | I1 検知に検出力あり |
| `_find_page` 戻り値を None 固定 | 2 failed (検出) | I2 顧客ID冪等に検出力あり |
| `_all_block_children` を先頭1ページのみに退化 | **0 failed (未検出)** | ページネーション境界が未カバー |
| `_find_page` の `len>1`→`len>99` | **0 failed (未検出)** | 顧客ID重複検出が未カバー |

→ 是正 (3 gap + I3 強化):
- `test_find_page_raises_on_duplicate_customer_id` (顧客ID重複 → RuntimeError)
- `test_upsert_paginates_beyond_100_rows_no_duplicate` (132ヶ月履歴の2ページ目を再sink→重複追記しない。fake store を 100件/ページ分割に拡張)
- `test_upsert_same_month_updates_correct_row_in_multirow_table` (多行tableで正しい月行だけ更新)
- `test_runtime_imports_are_stdlib_or_in_plugin_only` (I3 移植性の AST ガード)

→ 是正後の検出力を**自前のミューテーション再試行で実証** (`/tmp/mfk_mutation_proof.txt`):
先頭ページ退化 → `paginates_beyond` が exit1 で**検出**、`len>99` → `duplicate_customer` が exit1 で**検出**、
period_ym 一致破壊 → multirow/pagination が exit1 で**検出**。round1 で素通りした死角が塞がった。
フルスイート **45 passed / 2 skipped / exit 0**。

**round 2 — overall: ADEQUATE (R1 PASS / R2 PASS / R3 PASS)**

同レビュアが独立 context で M3/M4 を /tmp 複製に再注入し、今度は対応テストが**落ちる**(検出される)
ことを確認。追加で M5 (period 一致 `==`→`!=`) → multirow テスト検出、M6 (`import requests` 混入) →
I3 AST ガードが `{'lib/mfk_invoice_diff.py': ['requests']}` を正確に指摘、いずれも検出力を実証。
`concrete_gaps` 空。**自己検証ループ収束 (proposer ≠ approver を満たし完了)**。

---

## 7. deprecated 列移行 (P6, 実装済み)

データモデルを顧客ID集約へ変えた結果、旧『月次サマリ行』モデルの列
(レコード種別 / 発行漏れ件数 / 金額変動件数 / チェック件数合計) は未使用になった。

- schema (`notion-db-schema.json`) に `deprecated_properties` を宣言。
- `build_notion_db.ensure_schema`: 既存 DB にこれらの列があれば `properties.{name}=null` で
  **whitelist 削除**。安全制約として **schema の現行 properties に含まれる名前は決して削除しない**
  (誤削除防止。`tests/test_db_migration.py::test_build_never_deletes_a_current_schema_column` で担保)。
- `verify_db_schema`: 旧列が残存していれば **residual として FAIL (exit 1)**。掃除漏れを drift 検知。
- 回帰: `tests/test_db_migration.py` (7本)。build 削除を無効化 / verify residual 判定を無視する
  ミューテーションで対応テストが落ちる (検出力) ことを実証済み (`/tmp/mfk_p6_mutation.txt`)。
