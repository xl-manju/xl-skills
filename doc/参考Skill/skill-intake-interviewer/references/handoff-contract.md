---
name: handoff-contract
description: skill-creator への引き渡し JSON（intake-result.json）の正規スキーマ
type: reference
---

# ハンドオフ契約 JSON Schema

skill-intake-interviewer の最終出力 `intake.json` の正規スキーマ。
skill-creator はこの JSON を読み込んで Phase 0-0 を簡略化または飛ばす。

## ファイル配置

```
output/<skill-name-hint>/
├── intake.md          # 人間用・正本
├── intake.json        # skill-creator 用・副本（このスキーマ準拠）
├── notion-url.txt
└── slack-log.json
```

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
    "schema_version": {
      "type": "string",
      "const": "1.0.0"
    },
    "generated_at": {
      "type": "string",
      "format": "date-time"
    },
    "skill_name_hint": {
      "type": "string",
      "pattern": "^[a-z][a-z0-9-]*$",
      "description": "kebab-case 推奨スキル名（最終決定は skill-creator）"
    },
    "purpose": {
      "type": "object",
      "required": ["stated", "excavated", "jtbd"],
      "properties": {
        "stated": {
          "type": "string",
          "description": "ユーザーが最初に言った表層要望（原文）"
        },
        "excavated": {
          "type": "string",
          "description": "5 Whys 等で掘った真の課題"
        },
        "jtbd": {
          "type": "object",
          "required": ["when", "want_to", "so_i_can"],
          "properties": {
            "when": { "type": "string" },
            "want_to": { "type": "string" },
            "so_i_can": { "type": "string" }
          }
        },
        "magic_wand_vision": {
          "type": "string",
          "description": "制約を外した理想像"
        },
        "pain_stories": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "when": { "type": "string" },
              "what_happened": { "type": "string" },
              "felt": { "type": "string" },
              "cost_minutes": { "type": "number" }
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
        "role": { "type": "string" },
        "context": { "enum": ["業務", "個人", "学習", "趣味"] },
        "constraints": { "type": "array", "items": { "type": "string" } },
        "motivation": { "type": "string" },
        "share_target": { "enum": ["自分のみ", "少人数", "不特定多数", "顧客"] }
      }
    },
    "five_axes": {
      "type": "object",
      "required": ["output_target", "info_source", "share_target", "true_problem", "knowledge_assets"],
      "description": "5軸: 4軸（出力先/情報源/共有相手/真の課題）+ ナレッジ資産軸（MUST）",
      "properties": {
        "output_target": {
          "type": "object",
          "properties": {
            "answer": { "type": "string" },
            "depth": { "enum": ["quick", "standard", "deep"] },
            "verified": { "type": "boolean" }
          }
        },
        "info_source":   { "$ref": "#/properties/five_axes/properties/output_target" },
        "share_target":  { "$ref": "#/properties/five_axes/properties/output_target" },
        "true_problem":  { "$ref": "#/properties/five_axes/properties/output_target" },
        "knowledge_assets": {
          "type": "object",
          "required": ["needed", "verified"],
          "description": "思考プロセス・考え方・外部情報のナレッジ化に関する軸（MUST）",
          "properties": {
            "needed":   { "type": "boolean", "description": "ナレッジ注入が必要か" },
            "verified": { "type": "boolean" },
            "depth":    { "enum": ["quick", "standard", "deep"] },
            "existing_sources": {
              "type": "array",
              "description": "既存ナレッジの所在（Notion/Obsidian/メモ/チャットログ等）",
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
              "description": "取り込みたい外部情報（記事・論文・本・URL）",
              "items": {
                "type": "object",
                "properties": {
                  "title":   { "type": "string" },
                  "url":     { "type": "string" },
                  "purpose": { "type": "string" }
                }
              }
            },
            "tacit_knowledge": {
              "type": "array",
              "description": "暗黙知・口ぐせ・判断基準を言語化したもの",
              "items": { "type": "string" }
            },
            "extraction_pipeline": {
              "type": "object",
              "description": "外部情報→解析→保存→検索の流れ",
              "properties": {
                "needed":          { "type": "boolean" },
                "ingest_format":   { "type": "string", "description": "URL / PDF / テキスト / 音声 等" },
                "analysis_method": { "type": "string", "description": "要約 / 分類 / タグ付け / 埋め込み 等" },
                "storage":         { "type": "string", "description": "保存先（Notion/Obsidian/ベクタDB等）" },
                "retrieval":       { "type": "string", "description": "検索方法（キーワード/RAG等）" },
                "update_frequency":{ "enum": ["fixed", "manual", "weekly", "monthly", "on_demand"] }
              }
            },
            "exclusions": {
              "type": "array",
              "description": "ナレッジ化禁止情報（機密/個人情報/契約金額等）",
              "items": { "type": "string" }
            }
          }
        }
      }
    },
    "four_axes": {
      "type": "object",
      "deprecated": true,
      "description": "Deprecated: 後方互換用。five_axes を参照すること",
      "$ref": "#/properties/five_axes"
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
          "title": { "type": "string" },
          "status": { "enum": ["complete", "partial", "skipped"] },
          "filled_at": { "type": "string", "format": "date-time" }
        }
      }
    },
    "open_questions": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "question": { "type": "string" },
          "blocking": { "type": "boolean" },
          "deferred_to": { "enum": ["skill-creator", "later"] }
        }
      }
    },
    "recommended_next": {
      "type": "object",
      "required": ["mode", "skip_to_phase"],
      "properties": {
        "mode": { "enum": ["full", "fast-track", "verify-only"] },
        "skip_to_phase": { "type": "string", "description": "skill-creator の開始フェーズ識別子" },
        "rationale": { "type": "string" }
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
          "section": { "type": "string" },
          "svg_path": { "type": "string" },
          "one_liner": { "type": "string", "maxLength": 60 },
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
    "excavated": "セミナー告知の3日前に5分でフォームと集計まで完了させ、SNS拡散に時間を回したい",
    "jtbd": {
      "when": "セミナー告知の3日前",
      "want_to": "申込フォームを5分で作る",
      "so_i_can": "SNS拡散に時間を回せる"
    }
  },
  "user_profile": {
    "technical_level": "中級",
    "role": "個人事業主",
    "context": "業務",
    "share_target": "不特定多数"
  },
  "five_axes": {
    "output_target": { "answer": "Google Forms + Sheets", "depth": "standard", "verified": true },
    "info_source": { "answer": "セミナー概要メモ（手元）", "depth": "standard", "verified": true },
    "share_target": { "answer": "セミナー参加希望者（不特定多数）", "depth": "standard", "verified": true },
    "true_problem": { "answer": "告知準備の手作業90分の削減", "depth": "deep", "verified": true },
    "knowledge_assets": {
      "needed": true,
      "verified": true,
      "existing_sources": ["Notion 過去メモ30本"],
      "external_inputs": ["note 記事5本"],
      "tacit_knowledge": ["セミナー設計の型と禁則"],
      "exclusions": ["クライアント実名", "契約金額"]
    }
  },
  "workflow_pattern": "A",
  "completed_sheets": [
    { "section_id": "purpose", "title": "目的", "status": "complete" }
  ],
  "recommended_next": {
    "mode": "fast-track",
    "skip_to_phase": "Phase 1",
    "rationale": "5軸全充足（ナレッジ資産軸含む）、深度standard以上、類似スキル既存なし"
  }
}
```

## バリデーション

- `scripts/validate_intake.js` が schema 準拠を検証
- 必須欠落 → ヒアリング差し戻し
- `five_axes` の `verified=false` が1つでもあれば `recommended_next.mode="full"` 強制（ナレッジ資産軸含む）
