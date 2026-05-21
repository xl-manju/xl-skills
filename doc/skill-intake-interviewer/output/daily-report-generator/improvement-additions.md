# 追加要件（フェーズ3で適用）

## REQ-ADD-001: 日報の全文を自動的にナレッジ化

### 内容
作成した日報ファイル（YYYY-MM-DD_<概要>.txt）の本文をすべて、当該企業のナレッジ JSON に自動的に追記する。
これは従来の「ユーザーが良いと判断したものだけ samples に追加」の方針とは異なり、**全件を無条件で蓄積**する方式に変更。

### 目的
- 次回の日報作成時に「過去の自分が書いた日報全文」を文脈として参照可能にする
- トーン・粒度・固有名詞・継続案件の前回状態を踏襲できる
- 受け手が好む文体パターンの統計的学習素材として機能

### 実装

#### 新トピック追加: `daily-history`
- ファイル名: `_knowledge_<企業>_daily-history[_<年月>].json`
- 月ごとに分割（`_2026-04`, `_2026-05` ...）
- 既存 `samples` トピックは「特に良かった日報」用に残し、`daily-history` は全件無差別蓄積で別役割

#### entries[] スキーマ
```json
{
  "id": "report-2026-04-30",
  "date": "2026-04-30",
  "weekday": "木",
  "title": "契約書テンプレ整備とMeet議事録レビュー",
  "filename": "2026-04-30_契約書テンプレ整備とMeet議事録レビュー.txt",
  "body": "（日報本文 全文）",
  "items_count": 4,
  "overall_progress": 75,
  "total_hours": 4.0,
  "status_breakdown": {"完了": 1, "進行中": 1, "未着手": 1, "ブロック": 1, "保留": 0},
  "consultations_count": 4,
  "tags": [],
  "created_at": "2026-04-30T18:00:00+09:00"
}
```

#### 実行タイミング
- `write_report.js` 成功直後、`append_knowledge.js --topic daily-history --company <企業> --entry <JSON>` を呼ぶ
- 失敗時: 日報ファイル自体は保存済として、ナレッジ追記失敗を WARNING で通知（日報生成全体は失敗扱いにしない）

#### ローテーション
- 月単位の split_key 採用（`_2026-04`）
- 月をまたいだ初回追記時に新ファイル作成
- 同一月内で 500 行を超えた場合は連番フォールバック（`_2026-04_001`, `_2026-04_002`）

#### load_knowledge.js での扱い
- 次回日報生成時、`daily-history` の直近 N 件（既定: 7件 = 直近1週間相当）を文脈として注入
- 全期間注入はトークン爆発するため上限を設ける
- 直近データの優先度を高くする（最新を末尾に配置）

### スキーマ更新箇所
- `references/knowledge-schema.md` のトピック責務表に `daily-history` を追加
- `intake.json` の `knowledge_assets.topics` に追加（フェーズ3で同期）
- 自己進化フローに「日報生成時=直近daily-history読込／日報保存時=daily-history自動追記」を明記

### 影響を受けるモジュール
- `scripts/append_knowledge.js`: daily-history トピック対応
- `scripts/load_knowledge.js`: daily-history の読込件数上限ロジック追加
- `scripts/write_report.js`: 保存後に append_knowledge 呼び出し
- `agents/render-and-save.md`: フロー説明に「全文ナレッジ化」ステップを追加
- `references/knowledge-schema.md`: daily-history 章を追加
- `SKILL.md`: 「自己進化」節に全文ナレッジ化を明記
