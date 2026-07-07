---
name: run-mf-invoice-report
description: 前月と今月のMF掛け払い発行状況を比較して請求漏れレポートを出したいとき、年契約やトライアル完了などのイレギュラーを事情コメント付きで月次レポートDBへ冪等生成したいときに使う。
disable-model-invocation: false  # 自然文「前月と今月の請求書発行状況を比較して漏れレポートを出して」で自動起動させる。書込安全は既定 dry-run + --apply に --verified を要求するゲートで担保 (reconcile と同型: external-mutation でも model-invocable)。
user-invocable: true
argument-hint: "[--target YYMM] [--apply --verified]"
arguments: [target, apply, verified]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-07-07
version: 0.1.0
source: doc/ClaudeCodeスキルの設計書/
source-tier: internal
last-audited: 2026-07-07
audit-trigger: quarterly
responsibility_refs:
  - prompts/R1-collect.md
  - prompts/R2-classify.md
  - prompts/R3-verify.md
  - prompts/R4-render.md
manifest: workflow-manifest.json
feedback_contract: # per-skill 評価基準(SSOT=scripts/feedback_contract_ssot.py)
  max_iterations: 3
  criteria:
    - id: IN1
      loop_scope: inner
      text: 前月↔今月比較と 12 ヶ月フル遡り(差分該当取引先のみ)の年契約周期/トライアル完了/契約終了分類が test_mfk_period_report で機械検証でき、正常イレギュラーと真の発行漏れを取り違えず漏れチェック/取引先名/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの7列が『この左→右の順で』定義され各行で該当列が埋まる(停止/契約完了行の今月の金額・新規/継続漏れ行の先月の金額は意味的に空を許容)。両月未発行でも今月 verdict=GAP の継続漏れは要対応として emit し脱落させない(Notion title=取引先名・列6=テキスト説明・金額は税抜)
      verify_by: test
    - id: OUT1
      loop_scope: outer
      text: 同一対象月で 2 営業日目・3 営業日目相当のデータを与え連続実行しても C06 sink が同じ month_db_id を再利用し、当月 DB へ入力同定 {取引先×契約ID×商品} と stored key (取引先名,商品名) で同一行を 1 行へ収束させ (同月 2 回実行で重複行 0・日々追加・二重 DB 0・非破壊マージで run-1={A,B}→run-2={A,C} 後も当月 DB が {A,B,C} を保持=以前 run の行が消えない/clear-then-insert と区別可能・契約ID違いは要対応優先で collapse 計上)、月跨ぎでは新しい月の DB が指定トグル配下へ append 作成され newest-on-top の意図位置が placement で開示され過去月 DB が残ること、各イレギュラー行がなぜ先月あって今月なくて問題ないかの事情コメントを持ち分類不能な差分だけが真の発行漏れとして漏れチェックに残ることを受入テストが確認する
      verify_by: test
---

# run-mf-invoice-report

## Purpose & Output Contract

MF掛け払いの**前月↔今月の請求書発行状況を突合**し、状態遷移 (今月あり×前月あり=継続発行 / 今月あり×前月なし=新規・年→月切替 / 今月なし×前月あり=非請求事情確認→発行漏れ候補 / 今月なし×前月なし=対象外・ただし今月 verdict=GAP は継続漏れ→要対応) を分類して、**漏れチェック / 取引先名 / 商品名 / 先月の金額 / 今月の金額 / 先月と今月の比較 / コメント の 7 列を『この左→右の順で固定』**した月次レポートテーブルを生成する。継続発行 (今月あり×前月あり) も漏れチェック=正常として**全行 emit** し全請求書一覧を成す (非 emit は今月なし×前月なしで今月 verdict が GAP でない=正常抑制/元々請求なし のみ)。真の発行漏れ (単月遷移の漏れ + 両月未発行の継続漏れ) だけを漏れチェック=要対応に残し、年契約/年→月切替/トライアル完了/契約終了の正常イレギュラーには**なぜ問題ないかの事情コメント**を焼く。

**対象月の定義**: 今月=直近締め済みの請求対象月 (例: 2026-07-02 実行なら 2026-06 分=`2606`)、先月はその 1 ヶ月前 (`2605`)。実行日カレンダー月ではない。

出力先は**月次レポート DB** — 指定ページ『請求書発行チェック』のトグル見出し2配下に対象月ごとの DB を積層する。C06 sink 経由で当月分 DB へ書き、同月内の 2/3 営業日目再実行は入力同定 **{取引先(customer) × 契約ID(contract_id) × 商品(product)}** と C06 の stored key **(取引先名, 商品名)** で重複行を出さず**日々追加**する。固定 7 列に契約ID列は無いため契約IDは永続化せず、契約ID違いは要対応優先で 1 行へ収束し `collapsed_multi_contract` に計上する。非破壊マージにより以前 run で書いた行は今回入力に無くても削除しない。DB 構築/配置/冪等 upsert は C06 sink が所有する。

**入力**: `--target YYMM` (対象月・省略時は実行日から直近締め済み月を導出)。既定は dry-run (集計・分類のみ・Notion 書き込みゼロ)、月次レポート DB への反映を含む `--apply` は dry-run と二段確認完了を示す `--verified` を必須にする。
**出力**: 7 列レポートテーブル (title=取引先名・列6=テキスト説明・金額税抜) + 判定内訳サマリ (継続発行/新規・年→月切替/対象外/発行漏れ候補の件数)。
**完了条件**: dry-run で分類内訳を確認 (二段確認) し、`--apply --verified` で当月レポート DB へ 7 列行が冪等 upsert され、過去月 DB が履歴として残った状態。

> **⚠️ AI・開発者向け — 分類/照合/冪等 upsert は実装済み・自作禁止**: 前月↔今月の状態遷移分類・事情コメント生成・月次 DB への冪等 upsert は**完成・テスト済み**。**自前の比較スクリプトを書いたり、分類 (classify/compare/period_diff 相当) を新規実装したり、判定を `TODO(human)` で人間に書かせたりしてはならない**。正本は次の 3 実体:
> - **`scripts/mfk_period_report.py`** (C05・前月↔今月分類エンジン): 既存 `lib/mfk_reconcile.py` の per-月 verdict を入力に取り、状態遷移だけを分類する薄い差分エンジン。終了根拠の一次情報源は既存 `mfk_reconcile.has_end_basis`→verdict `SUPPRESS_ENDED` であり、自由文を再パースしない。
> - **`lib/mfk_reconcile.py`** (per-月 verdict の供給源・突合キー正規化 `normalize`/`extract_names`)。
> - **`scripts/notion_report_sink.py`** (C06・月次 DB sink): find-or-create + 非破壊冪等 upsert。DB 生成/列型写像は `skills/run-mf-invoice-db-setup/scripts/build_notion_db.py` を再利用する。
>
> 自然文で頼まれたら新規実装せず `/run-mf-invoice-report --target YYMM` を **dry-run → 二段確認 (`mfk-report-verifier`) → `--apply --verified`** の順で実行する。**機械強制**: `hooks/guard-mfk-no-reinvent.py` (PreToolUse) が、正本以外への状態遷移分類の再実装 (`def compare_*`/`def period_diff`/`def classify_*` 等) と本ドメインでの `TODO(human)` 書き込みを exit 2 で遮断する (prose 指示が出力スタイルに上書きされても効く機械層)。

## End-to-End Flow

```
[1 collect]  対象月を決定 (今月=直近締め済み請求対象月・先月=その1ヶ月前) →
             前月/今月の全取引先 MF発行実績を参照専用GET (lib/mfk_api.py) →
             既存 reconcile engine (lib/mfk_reconcile.py) で per-月 verdict を収集 →
             取引先×商品で状態遷移を抽出し、差分に現れた該当取引先のみ 12ヶ月分の発行履歴を追加取得 →
             請求確認シート由来の契約終了月も収集 →
             curr-verdicts / prev-verdicts / lookback-12mo / contract-end の JSON 入力を組む
[2 classify] mfk_period_report.py (C05) で前月↔今月の状態遷移をイレギュラー分類し各行の事情コメント生成
             → 分類済みレポート行 JSON (漏れチェック/取引先/商品/先月金額/今月金額/比較/コメント)
[3 verify]   mfk-report-verifier sub-agent (context:fork) で独立contextの二段確認。
             真の発行漏れを『問題ない』と誤って隠していないかを検証 (誤って対象外化した候補を差し戻す)
[4 render]   notion_report_sink.py (C06) で月次レポート DB へ非破壊冪等upsert
             (find-or-create・当月DBへ日々追加・二重DB 0・deleted常時0・newest-on-top intended_index/append fallback)
             ↑ MF APIは全GET / 変更系は hook(guard-mfk-readonly.py)で遮断。分類再発明は hook(guard-mfk-no-reinvent.py)で遮断
```

詳細は `workflow-manifest.json`、責務は `prompts/R1-R4`。dry-run (分類のみ) と `--apply` (Notion 書き込み) を分離し、分類内訳を確認してから適用することで二段確認を標準フローで要求する。C05/C06 は決定論 script、収集 (R1) と分類呼出→二段確認→冪等描画のオーケストレーションが本 skill の責務。

## DB ライフサイクル (月次スナップショット積層・作り直さない・履歴保全)

月次運用ではレポート DB を**対象月ごとに find-or-create し upsert で更新**する。C06 sink が、指定ページ『請求書発行チェック』(論理キー `report_parent_page`) 配下の指定トグル見出し2ブロック (論理キー `report_toggle_block`) の子として、対象月 (`YYMM`) の DB を title『請求漏れ比較レポート YYYY-MM』で探索し、実在すれば再利用 (`month_db_reused=true`・二重 DB を作らない)・無ければ作成する。親ページ ID/トグルブロック ID は `mf-kessai-config.default.json` の配布既定 (`notion.report_parent_page`/`report_toggle_block`) が供給し、別出力先にしたい場合のみ `.mf-kessai-config.json` (gitignore) で上書きする。

**履歴が消えない設計**: 月跨ぎでは新しい月の DB が指定トグル配下へ append 作成され、newest-on-top の意図位置 (`intended_index`) は `placement` で開示され、過去月 DB は履歴として残る。同月内の再実行は当月 DB へ入力同定 **{取引先 × 契約ID × 商品}** と stored key **(取引先名, 商品名)** で日々追加 (同一行は 1 行へ収束=重複行 0)。**非破壊マージ**: 以前の run で書いた行は今回入力に無くても当月 DB から削除しない (`deleted` 常時 0・clear-then-insert でない)。手動追記運用は無い前提ゆえ frozen 列は設けない。

> **列順 SSOT (固定 7 列)**: [漏れチェック(select), 取引先名(title=ページ名), 商品名(rich_text), 先月の金額(number/yen), 今月の金額(number/yen), 先月と今月の比較(rich_text=テキスト説明), コメント(rich_text)]。金額は税抜。列型写像は build_notion_db を再利用。固定 7 列に契約ID 列は無いため、当月 DB 内の 1 行は (取引先名, 商品名) で回収され、契約ID は入力同定用メタとして主キーに含むが persist しない (C06 の `_stored_key` が SSOT)。

## boundary (責務境界)

- **入力**: MF掛け払い実績 (参照専用 GET) + 既存 `mfk_reconcile` の per-月 verdict + 請求確認シート (契約終了月)。
- **出力**: 月次レポート DB (指定ページ『請求書発行チェック』のトグル見出し2配下) の冪等上書き。
- **MF への書き込みはしない** (GET のみ・変更系は hook `guard-mfk-readonly.py` で遮断)。
- イレギュラー分類の実体は **C05 エンジン**・月次 DB 構築/配置/冪等 upsert は **C06 sink** に委譲し、本 skill は収集→分類呼出→二段確認→冪等描画の**オーケストレーションに徹する**。
- **既存 reconcile/check スキルの再設計はしない** (単月照合=`run-mf-invoice-reconcile`、前月↔今月比較=本 skill と役割分離)。

## ゴールシーク実行

### ゴール (Goal)
前月↔今月の MF 発行状況を突合した結果——継続発行 (全行)・新規/年→月切替・対象外・発行漏れ候補——が 7 列レポート行として当月分レポート DB へ非破壊冪等 upsert され、正常イレギュラーには事情コメントが焼かれ、独立 context の sub-agent で「真の発行漏れを問題ないと隠していないか」を確認した上で、分類不能な差分だけが漏れチェック=要対応として残った状態。

### 目的・背景 (Why)
単月照合では拾えない前月↔今月の発行増減を一望し、正常イレギュラー (年契約期間内/トライアル完了/契約終了) と真の漏れを分離して**なぜ問題ないかをコメント説明**することで、経理の請求漏れ確認を最新状態で回すため。誤って正常化して真の漏れを隠す事故を防ぐため、候補は dry-run と独立 context の二段で確認する。

### 責務サマリと完了条件の正本

各責務の**完了条件の詳細は `prompts/Rn` の L5.3 完了チェックリストを正本 (SSOT)** とする (片側更新ドリフトを避けるため SKILL 側で再定義しない)。本節は俯瞰用の責務サマリのみ示す。

- **R1 collect** (`prompts/R1-collect.md`): 対象月を決定し前月/今月の全取引先 MF実績 (参照専用 GET) と per-月 verdict を収集、差分該当取引先のみ 12 ヶ月遡り、契約終了月を集め C05 入力 JSON を組む。
- **R2 classify** (`prompts/R2-classify.md`): `mfk_period_report.py` で状態遷移を分類し事情コメントを生成する (既存 verdict を消費・再パースしない)。
- **R3 verify** (`prompts/R3-verify.md`): sub-agent `mfk-report-verifier` が独立 context で「真の発行漏れを問題ないと隠していないか」を二段確認する。
- **R4 render** (`prompts/R4-render.md`): `notion_report_sink.py` で当月レポート DB へ 7 列行を非破壊冪等 upsert する (find-or-create・日々追加・過去月 DB 保全)。

### 完了チェックリスト (Checklist)
> 各責務の停止条件詳細は `prompts/Rn` の L5.3 を正本 (SSOT) とする。本節は俯瞰用の二値チェックのみ。
- [ ] 対象月 (今月=直近締め済み請求対象月・先月=その1ヶ月前) を決定し、前月/今月の MF実績と per-月 verdict を収集した (R1)
- [ ] 差分に現れた該当取引先のみ 12 ヶ月遡りの発行履歴と契約終了月を集めた (R1・全件遡らない=API 負荷最小化)
- [ ] `mfk_period_report.py` で状態遷移を分類し継続発行を全行 emit・正常イレギュラーに事情コメントを焼いた (R2)
- [ ] sub-agent `mfk-report-verifier` が独立 context で真の発行漏れを隠していないか二段確認した (R3)
- [ ] `--apply --verified` で当月レポート DB へ 7 列行を非破壊冪等 upsert した (重複行 0・二重 DB 0・deleted 0・R4)
- [ ] 月跨ぎで新しい月 DB が指定トグル配下へ append 作成され、newest-on-top の意図位置が placement で開示され、過去月 DB が履歴として残った (R4)
- [ ] トグルブロック ID 未設定時は fail-closed (exit 2) で差し戻した (--apply 時)

### ゴールシークループ
1. `--target` を決定し R1 で MF実績 + per-月 verdict + 12 ヶ月遡り + 契約終了月を収集 (`R1`)。
2. 既定 dry-run で `mfk_period_report.py` を回し分類内訳を得る (`R2`)。
3. sub-agent で二段確認し、正常化しすぎて隠れた真の漏れを差し戻す (`R3`)。
4. `--apply --verified` で当月レポート DB へ非破壊冪等 upsert (`R4`)。過去月 DB は保全。
5. 全 checklist 充足で完了。トグル ID 未設定なら fail-closed で差し戻す。

## Key Rules

1. **参照専用 (二層で抑止)**: 第1層=`hooks/guard-mfk-readonly.py` (PreToolUse) が Bash 経由の MF 変更系を遮断。第2層=`lib/mfk_api.py` は GET 専用で POST/PATCH/DELETE 関数を構造的に持たない。MF へは一切書き込まない。
2. **分類再発明の遮断**: `hooks/guard-mfk-no-reinvent.py` が正本 (`mfk_period_report.py`/`mfk_reconcile.py`/`reconcile_invoices.py`) 以外への状態遷移分類関数 (`compare`/`period_diff`/`classify_*` 語幹) の再実装と `TODO(human)` を exit 2 で遮断する。分類は C05 が正本。
3. **対象月は直近締め済み**: 今月=実行日カレンダー月の前月 (直近締め済み請求対象月)、先月はその 1 ヶ月前。MF の月帰属は `transaction.date` (取引日・月末締め) 軸で、C05 の `resolve_target_months` が導出する。
4. **全行 emit で全請求書一覧**: 継続発行 (今月あり×前月あり) も漏れチェック=正常として全行 emit する。非 emit は今月なし×前月なしのうち今月 verdict が GAP でない (正常抑制 SUPPRESS_*/元々請求なし) 行のみ。**両月未発行でも今月 verdict=GAP の継続漏れは要対応として emit** し脱落させない (単月照合と整合・漏れを隠さない)。真の発行漏れ (単月遷移の漏れ + 継続漏れ) だけを漏れチェック=要対応に残す。
5. **正常事情は既存 verdict を一次源に消費 (再パース禁止)**: 契約完了=`SUPPRESS_ENDED`、年契約期間内=`SUPPRESS_ANNUAL`/`MATCH_ANNUAL` を一次源にし、12 ヶ月遡りは根拠コメント補強に限定 (既存判定を上書きしない)。トライアル完了は canon 前の生商品名/MF 明細 desc の『トライアル』信号で判定。**根拠なき終了月** (`REVIEW_ENDED_NO_BASIS`) は抑制せず発行漏れ候補に残す (漏れ隠蔽防止の既存安全弁を保全)。
6. **12 ヶ月遡りは差分該当取引先のみ**: 前月↔今月の差分に現れた取引先だけ 12 ヶ月履歴を追加取得する (全件遡らない=API 負荷最小化)。
7. **二段確認 (dry-run + `--verified` が物理境界・機械強制)**: 既定は dry-run (分類のみ・書き込みゼロ)。月次 DB 反映を含む `--apply` は `--verified` 明示時だけ通す — これは prose の約束でなく `notion_report_sink.py` が `--apply` かつ `--verified` でなければ書込を拒否し exit 2 する**機械ゲート**である (MEMORY『保証要件は機械層で担保』)。分類内訳を dry-run で確認し、sub-agent の二段確認後にだけ `--apply --verified` を使う (誤投入防止)。
8. **月次 DB は作り直さず find-or-create**: 対象月 DB が実在すれば再利用 (二重 DB を作らない)。月跨ぎは新しい月 DB を append 作成し、newest-on-top の意図位置を `placement` で開示し、過去月 DB を履歴として残す。
9. **非破壊冪等 upsert**: 同月再実行は入力同定 {取引先 × 契約ID × 商品} と stored key (取引先名, 商品名) で同一行を 1 行へ収束 (重複行 0)。固定 7 列に契約IDは永続化しないため、契約ID違いは要対応優先で collapse し `collapsed_multi_contract` に計上する。以前 run の行は今回入力に無くても削除しない (`deleted` 常時 0)。
10. **列順は固定 SSOT**: [漏れチェック, 取引先名, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] を左→右順で固定。title=取引先名・列6=テキスト説明・金額は税抜。C06 の `COLUMN_ORDER` が正本。ただし **Notion table view は title 列 (取引先名) を最左に固定描画する**ため、実表示は 取引先名 → 漏れチェック → … になる (列定義順 SSOT と実描画順の差は Notion 仕様・sink 出力の `placement.column_order_note` で開示)。漏れチェックを最左表示にするには title を別列へ移す設計変更が要る。

## Gotchas

1. 出力先の親ページ『請求書発行チェック』(`notion.report_parent_page`) とトグル見出し2ブロック (`notion.report_toggle_block`) は XLOCAL 共有の本番出力先を `mf-kessai-config.default.json` に**焼き込み済み**で、導入者は設定不要でそのまま `--apply` できる。別ワークスペース/別トグルへ出力する場合のみ `.mf-kessai-config.json` (gitignore) で上書きする。`report_toggle_block` を空にすると `--apply` 時に fail-closed (exit 2)。dry-run はトグル未走査で完走する。
2. MF APIキーと Notion トークンは別 Keychain entry (`mfkessai-api-key.xl-skills` / `notion-api-key.xl-skills`、いずれも account=xl-skills)。
3. トグル配下 DB 生成 + newest-on-top 先頭挿入のうち**任意位置 insert は Notion API に存在しない** (child ブロックは末尾 append のみ)。C06 は意図位置 (`intended_index`) を YYYY-MM から算出し報告するが実配置は append となる (fallback=title の YYYY-MM で識別)。この差は sink 出力の `placement` フィールドで開示される。
4. 固定 7 列に契約ID 列は無い。当月 DB 内の 1 行は (取引先名, 商品名) で識別され、契約ID は入力同定用メタ (persist しない=既存ページから回収できない)。C05 は同一取引先・同一商品の複数契約を契約ID で別行に分離するが、C06 は 7 列に契約ID列が無いため (取引先名, 商品名) で 1 行に収束する。この収束時は **要対応 (発行漏れ候補) を正常が上書きしない safe guard** で漏れ隠蔽 (false-negative) を防ぎ、多契約 collapse 件数を stdout の `collapsed_multi_contract` に計上する (常態化すれば 8 列目 契約ID 追加への移行トリガ)。「多契約×同一商品は稀」という前提で 7 列固定を優先した設計判断。safe guard は **run 内 collapse だけでなく cross-run 更新にも対称に効く**: 前 run で立てた要対応行を次 run の正常が無条件上書きせず要対応を保持し、正常化した旨をコメントへ注記する。同 severity の要対応×要対応 collapse は両者のコメントを連結マージして片方の漏れ詳細を失わない。
5. カタカナが NFD (macOS/MF API 由来) でリテラル(NFC)と != になるため突合キーは `mfk_reconcile.normalize` (NFKC) を再利用する (自作正規化を発明しない)。
6. per-月 verdict は既存 reconcile engine の出力を消費する。C05 は verdict を再照合・再パースしないため、上流の verdict が誤っていれば分類も従う (真の漏れ判定は R3 の二段確認で担保)。
7. **月次レポート DB は機械専有 (machine-owned)**: C06 sink が冪等上書きする出力先で、経理の手動トリアージ (人間対応済み/確認メモ) は本 DB でなく単月照合の DB2 (`run-mf-invoice-reconcile` の月次チェック DB) で行う。本 DB に人が手で追記した select/コメントは翌日の非破壊 upsert で機械が上書きしうる (frozen 列を持たない=手動追記運用が無い前提)。経理は本 DB を「読んで確認する」用途で使い、対応記録は reconcile DB2 側に残す。
8. **今月の金額 (amount) の意味**: C05 は per-月 verdict を消費する薄い差分エンジンゆえ、`今月の金額` は MF 実発行額そのものでなく契約の現行単価/期待単価 (`mfk_reconcile` 由来) を優先して載せる。先月の金額と並置して増減の当たりを付ける用途で、厳密な実発行額照合は単月 `run-mf-invoice-reconcile` が担う。
9. **exit 1 は失敗でない**: `mfk_period_report.py` は発行漏れ候補 (要対応) が 1 件でもあると exit 1 を返す (正常な検出結果)。CI/オーケストレーションは fatal を exit 2 のみとし exit 1 を失敗扱いしないこと (workflow-manifest の classify phase に明記)。

## Additional Resources

- `workflow-manifest.json` — collect/classify/verify/render の Step 定義 + hook guard
- `$CLAUDE_PLUGIN_ROOT/scripts/mfk_period_report.py` — 前月↔今月分類エンジン (C05・既存 per-月 verdict を消費する薄い差分エンジン・network なし)
- `$CLAUDE_PLUGIN_ROOT/scripts/notion_report_sink.py` — 月次レポート DB 積層 sink (C06・find-or-create + 非破壊冪等 upsert)
- `$CLAUDE_PLUGIN_ROOT/lib/mfk_reconcile.py` — per-月 verdict 供給源 + 突合キー正規化 (normalize/extract_names)
- `$CLAUDE_PLUGIN_ROOT/lib/mfk_api.py` — MF掛け払い GET 専用クライアント
- `$CLAUDE_PLUGIN_ROOT/skills/run-mf-invoice-db-setup/scripts/build_notion_db.py` — DB 生成/列型写像 (C06 が再利用)
- `prompts/R1-collect.md`〜`R4-render.md` — 責務プロンプト (7 層構造)
- `$CLAUDE_PLUGIN_ROOT/hooks/guard-mfk-readonly.py` — 参照専用ガード / `guard-mfk-no-reinvent.py` — 分類再発明ガード
- `$CLAUDE_PLUGIN_ROOT/agents/mfk-report-verifier.md` — 二段確認 sub-agent (責務本文 SSOT=prompts/R3-verify.md)
