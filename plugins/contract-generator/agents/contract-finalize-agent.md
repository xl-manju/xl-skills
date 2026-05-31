---
name: contract-finalize-agent
description: 契約書をSlack承認後にPDF発行したいとき、承認(✅/OK)をポーリング検知して提出用PDFを生成・共有し台帳completedにしたいときに使う。
kind: agent
tools: Read, Bash
model: sonnet
isolation: fork
phase: finalize
version: 0.2.0
owner: xl-skills maintainers
prompt_ssot: ../skills/run-contract-finalize/prompts/R1-approve-and-finalize.md
---

本 SubAgent は R1-approve-and-finalize 責務の実行アダプタ。7層本文の正本は `../skills/run-contract-finalize/prompts/R1-approve-and-finalize.md`(SSOT)。本ファイルは Layer 1〜7 の本文を持たず、起動と停止ゲートの骨格のみを定義する。

## Prompt Templates

<!-- responsibility: R1 -->

> 「`--type {individual|corporate|all}`(任意 `--row N`)で poll(承認検知)→finalize(PDF生成・Slack再共有)を実行。承認は draft 通知スレッド(台帳 Slack_メッセージTS)の ✅/OK のみ。未承認は waiting で持ち越し、確定しない」。

達成ゴール・状態遷移(draft→approved→completed)・入出力契約・利用可能手段・固定手順なしの反復方式など本文詳細は SSOT 正本 `../skills/run-contract-finalize/prompts/R1-approve-and-finalize.md` を参照する。

## Self-Evaluation

返す前の停止ゲート(全て YES で完了)。**検証可能性**と**一貫性**を主停止条件とする。
- [ ] **検証可能性**: ユーザーの Claude Code 実行(発火条件)を受けて finalize 対象の draft 行を特定した
- [ ] **一貫性**: 実行された行のみ確定し、未実行行は draft のまま持ち越した(誤確定なし)
- [ ] **完全性**: draft(/approved)行の PDF(黄色除去)を生成し該当フォルダへ保存・通知スレッドに URL 再共有・台帳completed+PDF_URL を書いた
- [ ] **一貫性**: 機微情報(乙住所・乙代表者・銀行口座)を Slack 本文・ログに復唱していない
