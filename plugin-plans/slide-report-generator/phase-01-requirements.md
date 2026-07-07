---
id: P01
phase_number: 1
phase_name: requirements
category: 要件
prev_phase: 0
next_phase: 2
status: 未実施
gate_type: none
entities_covered: []
applicability:
  applicable: true
  reason: ""
---

# P01 — requirements (要件定義)

## 目的
既存 presentation-slide-generator(v8.4.2)の全機能を xl-skills plugin へ抜け漏れなく移植し、共通コア + output_mode=slide/report の 2 モード + report 新規機能を持つビジュアル生成ハーネスを目的ドリブンに要件化して、後続フェーズが参照する `goal-spec.json` を確定させる。target_plugin_slug=`slide-report-generator` を固定する。**本 update では追加要件として、report モードの出力を『情報の羅列』から『構造化された読み物レポート』へ引き上げる改善 (C9-C14) を要件化する** (既存 gate-green baseline への additive・slide 経路と意匠/技術 SSOT は無改変)。

## 改善要件 (report 構造化・C9-C14)

> 本節は goal-spec.source_improvement.ref の詳細正本。現状 report は「破綻しない HTML を決定論生成」には成功しているが、schema か renderer のどちらかで下記が欠落/デッド化しており「情報の羅列」に見える。6 根因 → 6 要件 (C9-C14) で 1:1 に閉じる。加えて本再検証 (30思考法) の再問いで、当初の defect-repair 分解 (欠落を直す 6 根因) の枠外にあった第7根因『読み物としての横断的読書体験 (節間フロー/読書タイポグラフィ/文書メタ/色覚アクセシビリティ/新 block 表現機構) が未評価』を発掘し、C15 (節間フロー throughLine/transition) 新設 + C9-C14 の additive 次元拡張 (schema 1.2.0) へ広げる。in-scope = C17/C18/C19/C24/C25 + schemas(report-structure additive 1.1.0→1.2.0)/references。新規 buildable component は増やさない (責務は既存 design/render/verify の分担に収まる no-split)。

| 根因 (現状の欠落) | 対応要件 | 焼き先 |
|---|---|---|
| 節内論理展開テンプレート不在 (`paragraphs[]` が自由文字列・narrative フィールド無し → 論理が LLM 自由作文任せで羅列退化) | C9 | schema `section.narrative` + C17 設計 + report-narrative-logic.md 正本 |
| block 構造 (markdown表/フェンスドコードブロック/番号リスト/小見出し) が render-report.js 未実装で潰れる (表が `<br>` 化) | C10 | schema `section.body[]` block 型 + C19 render-report.js 実装 |
| 強調が `**bold**`→accent 1種のみ (色付きハイライト/キーポイント/統計タイルが schema・renderer 双方に無い) | C11 | schema inline highlight/key-point/stat-tile トークン + C19 render + 意匠 accent 流用 |
| `placement.grid/zones/emphasis` が schema にあるが render-report.js が無視するデッドフィールド (図は常に段落末尾全幅) | C12 | C18 が決定・C19 render-report.js が反映 (placement live 化) |
| 品質ゲートが減点型 (空節/図解過多/順序崩れ/letterbox の破綻検出のみ)。「羅列でも破綻ゼロなら PASS」 | C13 | C24 積極評価 RQ21- + C25 機械チェック追加 |
| reportType 骨格が節順序どまりで「本質課題→解決→活用」と横断的な必須要素を全型で強制しない | C14 | report-narrative-logic.md の**開いた読書体験カタログ(再問い由来)** + 4 reportType 骨格へ additive 反映。文書メタ/per-section recap/表現機構(定義リスト・脚注引用・タスクリスト)を横断要素へ拡張 |
| **(第7根因・再問い由来)** 読み物としての横断的読書体験(文書全体の通し筋=節間フロー・読書タイポグラフィ・文書メタ・色覚アクセシビリティ・新 block 表現機構)が当初の defect-repair 6 根因分解の枠外で未評価 | C15 + C9-C14 additive | C15=throughLine/transition(C17 設計・C24 積極評価・C25 throughLine 非空機械検査)。C9-C14 additive= schema 1.2.0(section.role/文書メタ/新 block/highlight 第2チャネル/placement 正規化)+ report読書CSS(C19)+ 色覚非依存の強調(C11/C24/C25) |

## 背景
本プラグインは、単一 SKILL の巨大ハーネス(13 sub-agent / 42 references / 30 Node scripts / 118 templates / 7 schemas / Codex Image2 チェーン / 30種思考法評価 / A4印刷 / GASデプロイ)を plugin 化する構想から出発する。機能削減・平均回帰・オミットを禁じ、既存全資産が component か plugin-level surface に必ず対応することを要件の第一に据える。同一構想は常に同一 `PLAN_DIR` へ解決され(再現性アンカー)、以降のフェーズはこの goal-spec を唯一の起点にする。

## 前提条件
- 既存 presentation-slide-generator の実ソース(SKILL.md / agents / references / scripts / schemas / assets)が参照可能である。
- 移植元 root が存在する、または plan 同梱 `vendor-digest-manifest.json` (v8.4.2 byte 正本) で照合可能である(移植元不在環境では manifest 照合を代替とする)。
- 汎用の `run-goal-elicit`(harness-creator)で purpose/background/goal/checklist を抽出できる(再実装しない)。
- このフェーズは特定 component へ紐づかない(責務は goal-spec 確定・target_plugin_slug 固定)。

## ドメイン知識
- output_mode = slide | report の 2 分岐。意匠/技術層は単一 SSOT 共有・コンテンツ意図層のみモード別(purpose の中核語)。
- vendored Node engine = Node/CJS 製レンダリング/画像/印刷/検証エンジンを byte 維持で携行し Python 化しない不変原則(既存資産の毀損回避)。
- 抜け漏れ厳禁 = source-inventory §5 被覆チェックリストで既存全資産が component or surface へ対応することを保証する。
- その他の plan 全体用語(component_kind / 5 種 buildable / 2 軸直交等)は index `## ドメイン知識` を参照。

## 成果物
- `goal-spec.json`(purpose/background/goal/checklist/constraints/handoff_targets)。移植要件 C1-C8 に加え report 構造化改善 C9-C15(C15=節間フロー・再問い由来)と `source_improvement` を保持する。
- target_plugin_slug=`slide-report-generator` と plan_dir=`plugin-plans/slide-report-generator` の確定値。
- `source-inventory.md`(既存全資産 → component/surface の R2 分解正本・被覆チェックリスト)。

## スコープ外
- component 分解・schema 設計(P02 へ委譲)。
- ヒアリング機構の再実装(`run-goal-elicit` を引用するのみ)。
- 実装・build(P05 と後段 builder の責務)。

## 完了チェックリスト
- [ ] `goal-spec.json` が purpose を非空で保持し、受入観点が purpose 語彙から導出されている(要件 C1-C8 の被覆が確認できる)。
- [ ] report 構造化改善の要件 C9-C15 (節内論理展開/block構造/色付き強調/意味的図解配置/積極評価ゲート/本質的横断要素/節間フロー through-line) が goal-spec.checklist に明記され、根因→要件→焼き先(第7根因 C15 含む)が本 phase の「改善要件」節で追跡できる。
- [ ] target_plugin_slug が ASCII kebab(`slide-report-generator`)で確定し以降のフェーズが参照できる。
- [ ] 既存全資産(13 agents / 42 references / 30 Node scripts / 118 templates / 7 schemas / Codex Image2 / 30種思考法 / A4印刷 / GAS)が移植対象として goal-spec に明記されている。
- [ ] `check-plugin-goal-spec.py` が exit0(R1 goal-spec + plugin 固有アンカー充足)。

## 参照情報
- `source-inventory.md`(R2 分解正本・被覆チェックリスト §5)。
- `schemas/plugin-goal-spec.schema.json` / `scripts/check-plugin-goal-spec.py`。
- 後続 P02(この goal-spec を component 分解の入力とする)。
