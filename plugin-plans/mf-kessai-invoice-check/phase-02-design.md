---
id: P02
phase_number: 2
phase_name: design
category: 設計
prev_phase: 1
next_phase: 3
status: 未実施
gate_type: none
entities_covered: [C01, C02, C03, C04, C05, C06]
applicability:
  applicable: true
  reason: ""
---

# P02 — design (設計)

## 目的
P01 の要件を「改善デルタが要する機能クラスタ」から 5 種の component_kind へ写像し、C01〜C06 の 6 実体を `component-inventory.json` へ確定する。各 component の build_target・依存 DAG・quality_gates を確定し、plugin envelope (`.claude-plugin/plugin.json`) の draft を設計する owner フェーズ。

## 背景
既存 reconcile の上に前月↔今月比較という新次元を足す改善であり、5 種を対称に 1 つずつ埋めるのでなく、機能クラスタ (収集/描画オーケストレーション・分類・二段確認・手動起動・再発明遮断・月次 DB 積層 sink) を先に列挙してから component_kind へ写像する (Goodhart 回避)。本改善では C05 (`mfk_period_report.py`) を既存 per-月 verdict を入力に取る薄い差分エンジンとして新設し、C06 (`notion_report_sink.py`) を **月次スナップショット DB を積層する sink** として独立させる。C06 は毎月新しい DB を find-or-create し、指定ページ『請求書発行チェック』の指定トグル見出し2ブロック配下の先頭 (newest-on-top=新しい月を上部) へ配置し、過去月の DB は記録として保持する。同月内の再実行は月次 DB 一意キー (target_month + logical_parent + title) で同じ DB を再利用し、当月 DB へ upsert 主キー {取引先×契約ID×商品} で日々追加 (重複行 0・二重 DB 0)、月跨ぎは新規 DB を上部に構築する二軸の冪等性を持つ。C01 (report skill) はオーケストレーション (収集→分類呼出→二段確認→月次 DB への冪等描画) に徹する境界を設計する。C04 (hook) は新規 build ではなく既存 `guard-mfk-no-reinvent.py` への in-place 拡張 (SANCTIONED_BASENAMES に `mfk_period_report.py` 追加等) として設計し、C05 が新規 classify 系関数を持つため既存 guard に遮断されないよう `C05.depends_on=[C04]` で拡張が先行する順序を DAG へ焼く。

## 前提条件
- P01 の `goal-spec.json` が確定している。
- 5 種の component_kind の写像規約 (`references/component-domain.md`) と envelope 物理契約が参照できる。
- 既存 `lib/mfk_reconcile.py` の per-月 verdict・`lib/notion_reconcile_sink.py` の非破壊 upsert パターン・既存稼働 hook `guard-mfk-no-reinvent.py` (203 行・R1-R3/allowlist) を土台に再利用する方針が共有されている。

## ドメイン知識
正規化原則 (build_target/depends_on は inventory のみが保持) と kind 写像の判定核は index `## ドメイン知識` を参照。本フェーズ固有の差分: `placement_scope=plugin-root` で C05/C06 を `plugins/mf-kessai-invoice-check/scripts/` へ hoist する (独立単体テスト性の確保・既存 `scripts/reconcile_invoices.py` と同じ plugin-root 慣習)。C05 は既存 reconcile スキルとの分類共有を主張しない (reconcile 側に C05 消費 route は無い・over-claim を撤回)。C04 は `build_mode=extend-existing` として既存実装を保全しつつ SANCTIONED/`_REINVENT_DEF_RE`/`_DOMAIN_RE` を拡張する設計判断とする。C06 は親ページ ID/トグルブロック ID を plan 成果物へ焼かず論理キー (`report_parent_page`/`report_toggle_block`) のみ宣言し、実行時 `.notion-config.json` が具体値を供給する two-layer 分離を設計する。レポート列は漏れチェック/取引先名/商品名/先月の金額/今月の金額/先月と今月の比較/コメントの 7 列とし、C06 が当月 DB へ書く際に先月分と今月分の金額を並置する。

## 成果物
- `component-inventory.json` (build 軸の唯一 SSOT・全 6 component C01〜C06)。
- `envelope-draft/plugin.json` (manifest draft)。

## スコープ外
- 設計の合否判定 (P03 design-gate へ委譲・自己承認しない)。
- 受入 criteria の導出 (P04 へ委譲)。
- 実体の生成 (P05・実 `plugins/` へは書かない)。

## 完了チェックリスト
- [ ] 全 6 component (C01〜C06) が build_target 非空・builder/build_kind 整合・depends_on 非循環 (C05←C04, C01←[C05,C06], C02/C03←C01) で inventory に載っている。
- [ ] considered_component_kinds が 5 種全列挙され、plugin_level_surfaces の採否が明示されている。
- [ ] `envelope-draft/plugin.json` に manifest draft (entry_points / hooks 配線(不変) / distribution) が設計され、C04 の `build_mode=extend-existing` (既存 hooks 配線を変更しない) が明示されている。

## 参照情報
- `references/component-domain.md` / `references/phase-lifecycle.md`。
- 対象 component C01〜C06 (`component-inventory.json`)。後続 P03 (この設計を design-gate で審査する)。
