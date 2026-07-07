---
id: P05
phase_number: 5
phase_name: implementation
category: 実装
prev_phase: 4
next_phase: 6
status: 未実施
gate_type: tdd-green
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P05 — implementation (実装)

## 目的
全 6 component (C01〜C06) を後段 builder へ委譲して実体化し、P04 で設計した criteria を満たす (Green) 状態にする。build routing は `component-inventory.json` の依存 top-sort 順に実行する (phase 順 ≠ build 順)。

## 背景
build は phase 順ではなく component の依存 top-sort 順に走る。本改善では build 順序を **C04 (既存 hook の in-place 拡張・依存なし) と C06 (冪等 sink・依存なし) を先行させ、次に C05 (`depends_on: [C04]`・guard の SANCTIONED 拡張が完了して初めて生成可能) を build し、その後 C01 (`depends_on: [C05, C06]`) を build し、最後に C01 に依存する C02・C03 を build する** 順序 (C04, C06 → C05 → C01 → C02, C03) で確定する。C04 は新規生成でなく既存 203 行の hook (`R1-R3`/allowlist/`guard-mfk-readonly.py` 配線) を保全した Edit 差分適用 (`build_mode=extend-existing`) である点が他の component と異なる。手続き的な build 順は `handoff-run-plugin-dev-plan.json` の routes が SSOT であり、本フェーズはその実行結果 (到達状態) を宣言する。

## 前提条件
- P04 で C01/C05/C06 等の criteria が Red で確定している。
- `handoff-run-plugin-dev-plan.json` の routes が inventory 由来で用意されている (C04, C06 → C05 → C01 → C02/C03 の依存順)。
- 後段 builder (run-skill-create / run-build-skill / plugin-scaffold) が利用可能。

## ドメイン知識
build 順の不変条件 (inventory DAG の top-sort 順) と builder 種別の実行実体差は index/io-contract §9 を参照。本 plan 固有の差分: C05/C06 は `placement_scope=plugin-root` ゆえ `builder=plugin-scaffold` で `plugins/mf-kessai-invoice-check/scripts/` へ hoist される。C05 は `depends_on=[C04]` により、既存 guard の SANCTIONED_BASENAMES に `mfk_period_report.py` が追加され `_REINVENT_DEF_RE`/`_DOMAIN_RE` が拡張された後でなければ生成できない (新規 classify 系関数を持つため既存 guard に遮断される)。C04 の拡張は `build_args.preserve` (R1-R3/allowlist/guard-mfk-readonly.py 配線/plugin.json hooks 配線) を保持した Edit 差分として適用し、上書き破壊しない。C06 の実装は **月次スナップショット DB の積層** を実体化する: 対象月の DB が無ければ指定ページ『請求書発行チェック』(論理キー `report_parent_page`) の指定トグル見出し2ブロック (論理キー `report_toggle_block`) 配下の先頭 (newest-on-top) へ新規 DB を find-or-create し、同一対象月なら target_month + logical_parent + title で既存 month_db_id を再利用して二重 DB を作らず、当月 DB へ漏れチェック/取引先名/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 7 列でレポート行を upsert 主キー {取引先×契約ID×商品} で日々追加する。親ページ ID/トグルブロック ID は具体値を実装・plan 双方に焼かず、実行時 `.notion-config.json` から解決する。DB 生成と 7 列スキーマ/列型写像は既存 `build_notion_db.py` の `build_property` を再利用し title(=各行=ページの作成/ページ名)プロパティ=取引先名・列順を [漏れチェック, 取引先名, 商品名, 先月の金額, 今月の金額, 先月と今月の比較, コメント] に固定する(列6=テキスト説明・金額税抜)。upsert は非破壊マージ(以前 run の行を削除しない=deleted 0・以前の情報が消えない)、HTTP は `notion_transport._req` を単一正本としテストは req 引数でモック差し替え可、配置は target_month の YYYY-MM 昇順で安定挿入し、トグル配下 DB 生成/先頭挿入の Notion API 実現性は GAP-NOTION-TOGGLE-PLACEMENT の spike で確定する。C05 は契約完了を既存 `has_end_basis`→`SUPPRESS_ENDED` verdict の消費で実装し(自由文を再パースしない・根拠なき終了月は REVIEW_ENDED_NO_BASIS を保全)、年契約正常化は既存 `SUPPRESS_ANNUAL`/`MATCH_ANNUAL` を一次源にする(12 ヶ月遡りは補強のみ)。C04 の再発明シグネチャは語幹前方一致で焼き C05 実関数名と byte 一致を取る(名前ゆらぎ回帰テストを追加)。

## 成果物
- 全 6 component (C01〜C06) の実体 (skill/sub-agent/slash-command/hook/script×2) が build_target に生成された状態。
- `envelope-draft/plugin.json` を基にした plugin manifest 更新 (entry_points への新 3 component 追加・version bump)。

## スコープ外
- カバレッジ拡充・テスト網羅 (P06)。
- purpose 受入判定 (P07)。
- builder 自体の改修 (harness-creator 側の責務・gap は `open_issues` へ起票)。

## 完了チェックリスト
- [ ] 依存 top-sort 順 (C04, C06 → C05 → C01 → C02/C03) で全 component が build され、C01 の criteria が Green (受入テスト PASS) になる。
- [ ] build 実体パスが inventory の build_target と一致する。
- [ ] C04 が既存 R1-R3/allowlist を保全したまま `mfk_period_report.py` を SANCTIONED へ追加する Edit 差分として拡張され、C05/C06 が `plugins/mf-kessai-invoice-check/scripts/` へ実体化され単一 skill 配下へ退化していない。
- [ ] C06 が月次新規 DB を指定ページ『請求書発行チェック』のトグル見出し2配下へ append で find-or-create(既存 build_notion_db.build_property 再利用・title=取引先名・列順固定・newest-on-top の意図位置は intended_index で開示=Notion API は任意位置 insert 不可)し、同一対象月では既存 month_db_id を再利用して二重 DB を作らず、当月 DB へ入力同定 {取引先×契約ID×商品}・stored key (取引先名,商品名) で非破壊マージ日々追加(以前 run の行を消さない・7列固定に契約ID列なし=契約ID非永続で契約ID違いは要対応優先 collapse+collapsed_multi_contract 計上・--apply は --verified 必須で未指定 exit2)する実装として build されている。

## 参照情報
- `handoff-run-plugin-dev-plan.json` (build routing・`open_issues` の GAP-C04-EXTEND/GAP-SCRIPT-BUILDER) / `component-inventory.json` (依存 DAG)。
- 対象 component C01〜C06。後続 P06 (test-run)。
