---
name: handoff-contract
description: skill-creator (run-skill-create) への引き渡し JSON (intake.json) の正規スキーマ
type: reference
---

# ハンドオフ契約 JSON Schema

`skill-intake-handoff` SubAgent の最終出力 `intake.json` の正規スキーマ。`run-skill-create` はこの JSON を読み込んで Phase 0-0 を簡略化または飛ばす。

## ファイル配置

```
output/<skill-name-hint>/
├── intake.md            # 人間用・正本
├── intake.json          # skill-creator 用・副本（このスキーマ準拠）
├── notion-url.txt       # 公開後の Notion URL
├── notion-blocks.json   # dry-run 用 Notion ブロック JSON
└── self-update.json     # question-bank への追記候補
```

Slack ログは本スキルのスコープ外（差別化済み）。

## JSON Schema（draft-07）

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "IntakeResult",
  "type": "object",
  "required": [
    "schema_version",
    "skill_name_hint",
    "purpose",
    "user_profile",
    "five_axes",
    "workflow_pattern",
    "completed_sheets",
    "recommended_next"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0.0" },
    "generated_at": { "type": "string", "format": "date-time" },
    "skill_name_hint": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$",
      "description": "kebab-case 推奨スキル名 (最終決定は run-skill-create)"
    },
    "purpose": {
      "type": "object",
      "required": ["stated", "excavated", "jtbd"],
      "properties": {
        "stated":   { "type": "string", "description": "表層要望（原文）" },
        "excavated":{ "type": "string", "description": "5 Whys 等で掘った真の課題" },
        "jtbd": {
          "type": "object",
          "required": ["when", "want_to", "so_i_can"],
          "properties": {
            "when":     { "type": "string" },
            "want_to":  { "type": "string" },
            "so_i_can": { "type": "string" }
          }
        },
        "magic_wand_vision": { "type": "string" },
        "pain_stories": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "when":          { "type": "string" },
              "what_happened": { "type": "string" },
              "felt":          { "type": "string" },
              "cost_minutes":  { "type": "number" }
            }
          }
        }
      }
    },
    "user_profile": {
      "type": "object",
      "required": ["technical_level", "role", "context"],
      "properties": {
        "technical_level": { "enum": ["非技術", "中級", "上級"] },
        "role":            { "type": "string" },
        "context":         { "enum": ["業務", "個人", "学習", "趣味"] },
        "constraints":     { "type": "array", "items": { "type": "string" } },
        "motivation":      { "type": "string" },
        "share_target":    { "enum": ["自分のみ", "少人数", "不特定多数", "顧客"] }
      }
    },
    "five_axes": {
      "type": "object",
      "required": ["output_target", "info_source", "share_target", "true_problem", "knowledge_assets"],
      "description": "5 軸: 4 軸 (出力先/情報源/共有相手/真の課題) + ナレッジ資産軸 (MUST)",
      "properties": {
        "output_target": {
          "type": "object",
          "properties": {
            "answer":   { "type": "string" },
            "depth":    { "enum": ["quick", "standard", "deep"] },
            "verified": { "type": "boolean" }
          }
        },
        "info_source":  { "$ref": "#/properties/five_axes/properties/output_target" },
        "share_target": { "$ref": "#/properties/five_axes/properties/output_target" },
        "true_problem": { "$ref": "#/properties/five_axes/properties/output_target" },
        "knowledge_assets": {
          "type": "object",
          "required": ["needed", "verified"],
          "properties": {
            "needed":   { "type": "boolean" },
            "verified": { "type": "boolean" },
            "depth":    { "enum": ["quick", "standard", "deep"] },
            "existing_sources": {
              "type": "array",
              "items": {
                "type": "object",
                "required": ["type", "location"],
                "properties": {
                  "type":     { "enum": ["notion", "obsidian", "memo", "chat_log", "file", "url", "book", "video", "other"] },
                  "location": { "type": "string" },
                  "summary":  { "type": "string" }
                }
              }
            },
            "external_inputs": {
              "type": "array",
              "items": {
                "type": "object",
                "properties": {
                  "title":   { "type": "string" },
                  "url":     { "type": "string" },
                  "purpose": { "type": "string" }
                }
              }
            },
            "tacit_knowledge": { "type": "array", "items": { "type": "string" } },
            "extraction_pipeline": {
              "type": "object",
              "properties": {
                "needed":           { "type": "boolean" },
                "ingest_format":    { "type": "string" },
                "analysis_method":  { "type": "string" },
                "storage":          { "type": "string" },
                "retrieval":        { "type": "string" },
                "update_frequency": { "enum": ["fixed", "manual", "weekly", "monthly", "on_demand"] }
              }
            },
            "exclusions": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "workflow_pattern": {
      "enum": ["A", "B", "C", "D", "E"],
      "description": "A=対話生成 / B=自動収集配信 / C=対話契約書 / D=分析レポート / E=その他"
    },
    "completed_sheets": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["section_id", "title", "status"],
        "properties": {
          "section_id": { "type": "string" },
          "title":      { "type": "string" },
          "status":     { "enum": ["complete", "partial", "skipped"] },
          "filled_at":  { "type": "string", "format": "date-time" }
        }
      }
    },
    "open_questions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "question":    { "type": "string" },
          "blocking":    { "type": "boolean" },
          "deferred_to": { "enum": ["skill-creator", "later"] }
        }
      }
    },
    "recommended_next": {
      "type": "object",
      "required": ["mode", "skip_to_phase"],
      "properties": {
        "mode":          { "enum": ["full", "fast-track", "verify-only"] },
        "skip_to_phase": { "type": "string" },
        "rationale":     { "type": "string" }
      }
    },
    "visualizations": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["type", "section", "svg_path", "one_liner"],
        "properties": {
          "type": {
            "enum": [
              "flowchart", "sequence", "state", "class", "er", "gantt",
              "pie", "mindmap", "timeline", "journey", "quadrant", "sankey",
              "numbered-steps", "persona-card", "before-after",
              "comparison-table", "traffic-light", "progress-bar",
              "icon-grid", "sankey-aux"
            ]
          },
          "section":        { "type": "string" },
          "svg_path":       { "type": "string" },
          "png_path":       { "type": "string" },
          "one_liner":      { "type": "string", "maxLength": 60 },
          "non_tech_score": { "type": "integer", "minimum": 1, "maximum": 3 }
        }
      }
    }
  }
}
```

## 必須フィールド最小例（google-forms-generator）

```json
{
  "schema_version": "1.0.0",
  "skill_name_hint": "google-forms-generator",
  "purpose": {
    "stated": "申込フォームを自動で作りたい",
    "excavated": "セミナー告知の 3 日前に 5 分でフォームと集計まで完了させ、SNS 拡散に時間を回したい",
    "jtbd": {
      "when": "セミナー告知の 3 日前",
      "want_to": "申込フォームを 5 分で作る",
      "so_i_can": "SNS 拡散に時間を回せる"
    }
  },
  "user_profile": { "technical_level": "中級", "role": "個人事業主", "context": "業務", "share_target": "不特定多数" },
  "five_axes": {
    "output_target": { "answer": "Google Forms + Sheets", "depth": "standard", "verified": true },
    "info_source":   { "answer": "セミナー概要メモ (手元)", "depth": "standard", "verified": true },
    "share_target":  { "answer": "セミナー参加希望者", "depth": "standard", "verified": true },
    "true_problem":  { "answer": "告知準備 90 分→10 分", "depth": "deep", "verified": true },
    "knowledge_assets": { "needed": true, "verified": true }
  },
  "workflow_pattern": "A",
  "completed_sheets": [{ "section_id": "purpose", "title": "目的", "status": "complete" }],
  "recommended_next": { "mode": "fast-track", "skip_to_phase": "Phase 1", "rationale": "5 軸全充足" }
}
```

## バリデーション

- `scripts/validate_intake.js` が schema 準拠を検証
- 必須欠落 → ヒアリング差し戻し
- `five_axes.*.verified=false` が 1 つでも残れば `recommended_next.mode="full"` 強制
- `knowledge_assets.verified` は **MUST**（false は不可、`needed=false` の verified=true は OK）

## `run-skill-elicit` との互換

`run-skill-elicit` が生成する brief.json も、本スキーマの `five_axes` 部分を空オブジェクトとして許容することで吸収できる。`run-skill-create` 側は両者を区別せず読み込めるよう、本スキーマを上位互換として運用する。
