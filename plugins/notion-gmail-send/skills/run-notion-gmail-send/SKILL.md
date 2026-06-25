---
name: run-notion-gmail-send
description: Notionメール本文DBの内容を対象者DBへGmailで一斉個別送信したいとき、差し込み置換して送りたいときに使う。
disable-model-invocation: true
user-invocable: true
argument-hint: "[--plan <plan.json>] [--config <path>] [--approved-nonce <確認語>] [--allow-resend]"
arguments: [plan]
allowed-tools:
  - Read
  - Write
  - Bash(python3 *)
  - Task
kind: run
prefix: run
effect: external-mutation
owner: team-platform
since: 2026-06-24
version: 0.1.0
source: doc/run-notion-gmail-send-仕様と検証メモ.md
source-tier: internal
last-audited: 2026-06-24
audit-trigger: runtime-failure
responsibility_refs:
  - prompts/R1-orchestrate.md
  - prompts/R2-presend-verify.md
schema_refs:
  - schemas/send-verdict.schema.json
---

# run-notion-gmail-send

## Purpose & Output Contract

dry-run で生成・承認された `plan.json` の各送信単位を、live-send preflight (G1/G2/G3) と `send_guard` を通して Gmail API で1通ずつ送信し、各結果を Notion 送信ログDBへ事前予約つきで冪等記録する不可逆送信の制御層。

**入力**: `plan`（任意。未指定なら最新の `plan.json`。無ければ dry-run へ誘導）+ 人間承認文字列 `APPROVE <plan_hash> <count> <first_to> <確認語>`
**出力**: Gmail 送信 + 送信ログDB の reserved→sent/unknown 記録 + 日本語送信レポート（送信/スキップ/失敗/要照合の件数・内訳・次アクション）
**完了条件**: 承認済み plan の全送信単位が「送信(sent) / 冪等スキップ / 検証スキップ / 要照合」のいずれかに確定し、ログDBへ反映された状態。外部実体未確定・plan不一致・reserved不在では **1通も送らず** fail-closed 中断・誘導。

## End-to-End Flow

```
[1 dry-run]   Skill(run-notion-gmail-dry-run) → plan.json + APPROVE文字列 + 全件プレビュー
[2 承認]      人間が差し込み後フル本文を目視 → APPROVE <plan_hash> <count> <first_to> <確認語> を入力
[3 二段確認]  Task(gmail-send-presend-verifier, context:fork) が plan を独立再計算で検査
[4 preflight] send_campaign.py が G1認証/G2依存実体/G3整合を fail-closed 検証
[5 予約+送信] 各単位を Notion へ reserved 事前予約 → send_guard 通過 → Gmail 送信 → sent/unknown 更新
[6 レポート]  日本語送信レポート (sent/skip/error/要照合)
              ↑ Gmail 直接送信は hook(guard-gmail-send.py)が補助遮断、正本は send_guard
```

責務は `prompts/R1-orchestrate.md`(統括) / `prompts/R2-presend-verify.md`(二段確認 SSOT)。

## ゴールシーク実行

### ゴール (Goal)
承認済み plan の各送信単位が、決定論セルフチェック（units→plan_hash/件数/content_hash を再計算照合）・preflight 全通過・reserved 事前予約・`send_guard` 通過を経て Gmail 送信され、結果が Notion 送信ログDBへ content ベース冪等キー `{本文page_id}:{宛先page_id}:{content_hash}`（campaign_id 非依存）で記録され、日本語レポートが提示された状態。外部実体未確定・plan_hash 不一致・件数偽装・確認語不一致・reserved 不在では1通も送らず中断・誘導した状態。

### 目的・背景 (Why)
不可逆な外部副作用 (メール送信) を三本柱で安全化する制御層。(1) 承認済み plan（送信前に units から plan_hash/件数/content_hash を**決定論再計算で束縛**し plan.json 改竄・件数偽装を機構で弾く）、(2) 人間承認ゲートは誤本文・誤宛先の**送信を止める停止点**で、確認語により blind approve のコストを上げる（ただし「人間が読み理解した」ことは機構で強制できず最終的な内容妥当性は目視に依存）、(3) content ベース冪等ログが再実行・別実行の二重送信と送信成功後ログ失敗を防ぐ。三者は役割が異なり混同しない (因果ループ警告 §2)。固定手順では入力 (plan有無/承認文字列/外部依存状態/quota) に脆いため、未達ゲートを都度埋める。

### 責務サマリと完了条件の正本
各責務の停止条件詳細は `prompts/Rn` を正本 (SSOT) とし、本節は俯瞰のみ示す (片側更新ドリフト回避)。
- **R1 orchestrate** (`prompts/R1-orchestrate.md`): preflight 統括・dry-run 委譲・`APPROVE <plan_hash> <count> <first_to> <確認語>` 形式の人間承認受領・送信可否判断・最終レポート生成。
- **R2 presend-verify** (`prompts/R2-presend-verify.md` / agent `gmail-send-presend-verifier`): context:fork で plan を独立再検査 (plan_hash/件数/先頭To/未置換トークン/宛先形式)。
- 決定論本体: `scripts/send_campaign.py`(reserve→send_guard→Gmail→log) / `scripts/verify_plan.py`(二段確認の計算) / `../../lib/`。

### 完了チェックリスト (Checklist)
- [ ] `run-notion-gmail-dry-run` で plan.json と APPROVE文字列・全件プレビューを得た
- [ ] 人間が差し込み後フル本文を目視し `APPROVE <plan_hash> <count> <first_to> <確認語>` を完全一致で入力した
- [ ] `Task(gmail-send-presend-verifier)` (context:fork) の verdict が pass (plan_hash/件数/先頭To/未置換/宛先 整合)
- [ ] `send_campaign.py` の preflight G1(認証)/G2(送信ログDB・本文true≥1)/G3(承認整合) が全 PASS
- [ ] 各送信単位を送信ログDBへ reserved 事前予約し、既存 sent/reserved/unknown は自動再送しなかった
- [ ] `send_guard` 通過後のみ Gmail 送信し、sent / unknown_needs_reconcile を記録した
- [ ] quota 安全停止時は残件を reserved のまま次回再開対象にした
- [ ] 日本語送信レポート (sent/skip/error/要照合の件数・内訳・次アクション) を提示した

### ゴールシークループ
正本 `../run-notion-gmail-dry-run/SKILL.md` 同様、未達チェックリスト項目を埋める手順を都度生成する。
1. plan.json が無ければ `run-notion-gmail-dry-run` を起動し plan と APPROVE文字列を得る。
2. 人間に全件プレビューを目視させ、`APPROVE <plan_hash> <count> <first_to> <確認語>` を受領する。承認なしに次へ進まない。
3. `Task(gmail-send-presend-verifier)` を context:fork で起動し plan を独立再検査。fail なら送信せず差し戻す。
4. `python3 "$CLAUDE_PLUGIN_ROOT/skills/run-notion-gmail-send/scripts/send_campaign.py" --plan <plan.json> --approved-plan-hash <h> --approved-count <n> --approved-first-to <to> --approved-nonce <確認語>` を実行（意図的再送のみ `--allow-resend`）。決定論セルフチェック・preflight 未充足なら誘導 (GCP手順/db-setup/本文記入) し中断。
5. 全 checklist 充足で完了。quota 停止 (exit 3) なら再実行で残件継続。

### ゴールシーク配線
quota 安全停止後の再開や verify FAIL 後の再試行で多周回する場合の周回状態。周回末に `eval-log/notion-gmail-send/run-notion-gmail-send-intermediate.jsonl` へ `{iteration, original_goal, current_goal_snapshot, delta_from_original, merged_directive_for_next, drift_signal}` を1行追記する。`original_goal` は全周回で不変 (SHA-256 を `eval-log/notion-gmail-send/run-notion-gmail-send-progress.json` の `original_goal_hash` に固定し毎周回照合)。次周回の手順生成は直前の `merged_directive_for_next` と `original_goal` を必須入力とする (AI 単独再導出禁止)。単発キャンペーンでは1周で完了し本配線は no-op。冪等ログが部分再開の物理的な起点となる。冪等キーは content ベース (campaign_id 非依存) なので、再開時に campaign_id を維持する必要はなく、別実行で同一 plan.json を使い直しても既 sent 単位は機構で skip される。

## Key Rules

1. **承認なしに本送信しない**: dry-run 全件プレビュー目視 → `APPROVE <plan_hash> <count> <first_to> <確認語>` 完全一致を必須化。自動本送信禁止。
2. **send_guard が正本防御**: `lib/gmail_client.py` が `lib/send_guard.py` を内部で必ず呼び、approved_plan_hash/件数/先頭To/reservedログ行/未置換トークン/From検証が揃わない限り Gmail API へ到達しない。PreToolUse hook (`guard-gmail-send.py`) は補助。
3. **reserved 事前予約なしに送信しない**: 送信前に Notion ログへ reserved を作り、同一冪等キーが sent/reserved/unknown なら自動再送しない。2行以上は `duplicate_log_key` で fail-closed。
4. **送信成功後ログ失敗は unknown_needs_reconcile**: ローカル journal に退避し自動再送しない。
5. **context:fork で二段確認**: Sycophancy 防止のため verify は必ず独立 context (`gmail-send-presend-verifier`)。
6. **sent は到達保証でない**: status=sent は Gmail API 受理を意味し受信者到達を保証しない。
7. **外部実体未確定は fail-closed**: SA鍵/DWD/sendAs/送信ログDB ID/本文記入が未充足なら送信せず誘導する。

## Gotchas

1. SA鍵/DWD/sendAs 未設定なら G1 で停止 → `../ref-gmail-dwd-setup/` と `doc/GCP-Gmail送信設定手順.md`。
2. 送信ログDB 未構築/未設定なら G2 で停止 → `../run-notion-gmail-sendlog-setup/`。
3. plan.json はソース変更後に dry-run を再生成して使う。ソースが変わったのに古い plan を使うと、新 dry-run の plan_hash/承認文字列が変わり古い承認は通らない。なお**同一の古い plan.json をその承認文字列ごと再利用**した場合は内部整合するため guard では止まらないが、既に送った単位は content ベース冪等ログが skip するため二重送信にはならない。
4. quota 停止 (exit 3) 後は再実行で残件を継続（停止単位は reserved へ戻り自動再開対象）。dedup は content ベースなので campaign_id 維持は不要。
5. 同一内容を**意図的に**再送する場合のみ `--allow-resend`（既定はクロス実行の二重送信を機構で防止）。
6. 承認には dry-run がプレビュー該当単位の行末にのみ表示する `<確認語>` が必要。`APPROVE <plan_hash> <count> <first_to> <確認語>` を完全一致で入力する（blind approve 防止）。
7. `multi_to_visible` の送信単位は To 受信者が互いのアドレスを見られる。承認 echo で必ず確認する。
8. 送信前に `run-notion-gmail-source-audit` でソース2DB の品質を整えると skip を減らせる。

## Additional Resources

- `scripts/send_campaign.py` — live-send 本体 (preflight→reserve→send_guard→Gmail→log→report)
- `scripts/verify_plan.py` — 送信前二段確認の独立再計算
- `prompts/R1-orchestrate.md` / `prompts/R2-presend-verify.md` — 責務プロンプト
- `../ref-notion-gmail-send-spec/` — データ契約・安全設計の参照正本
- `../run-notion-gmail-dry-run/` — plan.json と APPROVE文字列を生成する前段
- `../../agents/gmail-send-presend-verifier.md` — context:fork 二段確認 subagent
- `../../lib/` — send_guard / gmail_client / idempotent_log / plan_build / preflight ほか
- `../../hooks/guard-gmail-send.py` — Gmail 直接送信の補助遮断
