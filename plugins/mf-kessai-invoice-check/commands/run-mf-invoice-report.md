---
name: run-mf-invoice-report
description: 前月↔今月のMF掛け払い発行状況を比較して漏れレポートを手動起動したいとき、2営業日目以降に何度でも冪等再実行して専用DBへ上書きしたいときに使う。
argument-hint: "[--target YYMM] [--apply --verified]"
allowed-tools: Read, Bash, Skill
kind: command
version: 0.1.0
owner: team-platform
since: 2026-07-07
source: doc/ClaudeCodeスキルの設計書/
entrypoint: run-mf-invoice-report
---

# /run-mf-invoice-report

`$ARGUMENTS` を `run-mf-invoice-report` スキルに渡し、MF 掛け払いの**前月↔今月の請求書発行状況を突合**して発行漏れ比較レポートを生成する。今月=直近締め済みの請求対象月 (例 2026-07-02 実行なら 2026-06 分=`2606`)、先月はその 1 ヶ月前 (`2605`)。2 営業日目以降に何度でも冪等再実行でき、専用の月次レポート DB へ日々追加 (非破壊マージ) する。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-report`。

## 振る舞い

1. `Skill(run-mf-invoice-report, args="$ARGUMENTS")` を呼ぶ。
2. 既定は **dry-run** (分類・集計のみ・Notion 書き込みゼロ)。collect→classify を回し、継続発行/新規・年→月切替/対象外/発行漏れ候補の判定内訳を提示する。
3. 独立 context の `mfk-report-verifier` で二段確認 (真の発行漏れを『問題ない』と誤って隠していないかの差し戻し) したのち、`--apply --verified` を付けたときだけ当月レポート DB へ 7 列行を非破壊冪等 upsert する。
4. 出力先の親ページ『請求書発行チェック』(`notion.report_parent_page`) とトグル見出し2ブロック (`notion.report_toggle_block`) は配布既定 `mf-kessai-config.default.json` に焼き込み済みで設定不要。別ワークスペース/別トグルへ出す場合のみ `.mf-kessai-config.json` で上書き。`report_toggle_block` を空にすると `--apply` 時 fail-closed (exit 2)。

## レポート列 (7 列・金額は税抜)

生成 DB は次の 7 列を持つ (列定義はこの左→右順・**金額は税抜**)。継続発行 (今月あり×前月あり) も正常として全行 emit し、真の発行漏れ (継続漏れを含む) だけが「漏れチェック=要対応」に残る。

| 列 | 内容 |
|---|---|
| 漏れチェック | `正常` / `要対応` (発行漏れ候補) |
| 取引先名 | Notion の title (ページ名)。※Notion table view は title を最左固定で描画するため実表示は取引先名が先頭列 |
| 商品名 | 対象商品 |
| 先月の金額 | 先月分の税抜金額 (停止/契約完了行は空) |
| 今月の金額 | 今月分の税抜金額 (新規/継続漏れ行は空のことがある) |
| 先月と今月の比較 | 状態ラベル (継続発行 / 新規・年→月切替 / 契約完了 / 継続 等) |
| コメント | 年契約・契約終了・トライアル完了などの正常事情、または要対応の根拠 |

## 実行コード

スラッシュが使えない環境では、プラグイン配下の分類エンジン + sink を直接実行する (既定 dry-run)。C05 の `--target-month` と C06 の `--target` は必ず同じ対象月 (YYMM) を渡すこと。ズレていると sink が誤月 DB への投入を防ぐため fail-closed (exit 2) で中止する。

```bash
# 1) 前月↔今月分類 (参照専用・dry-run)。curr/prev の per-月 verdict は R1 collect が組む
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/mfk_period_report.py" \
  --curr-verdicts curr.json --prev-verdicts prev.json \
  --lookback-12mo lookback.json --contract-end ends.json --target-month 2606 > rows.json

# 2) 月次レポート DB へ非破壊冪等 upsert (--apply --verified で書き込み)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/notion_report_sink.py" \
  --rows rows.json --target 2606                # dry-run (計画のみ・書き込みゼロ)
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/scripts/notion_report_sink.py" \
  --rows rows.json --target 2606 --apply --verified   # 当月 DB へ upsert (日々追加・非破壊)。--verified 必須 (未指定は exit2)
```
