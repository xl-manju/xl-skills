# Notion スキーマ SSOT

xl-skills のプラグイン量産フローを Notion 上の 3 DB と連動させるための schema-as-code 定義。

## 構成

| ファイル | 対応 Notion DB | DB ID |
|---|---|---|
| `hearing-sheet.schema.json` | Skillヒアリングシート | `36607a0c-d18c-80bf-9eff-c74aa736645c` |
| `skill-list.schema.json` | Skill一覧（プラグイン単位） | `36b07a0c-d18c-8073-b106-e70552e13308` |
| `improvement-request.schema.json` | Skill改善要望 | `36b07a0c-d18c-80db-aae0-d713838cd6f4` |

## リレーション

```
ヒアリングシート ──(1:1)── スキル一覧 ──(1:N)── 改善要望
   紐づくプラグイン       紐づくヒアリングシート / 改善要望     対象プラグイン
```

- ヒアリングシート 1 件 = プラグイン 1 件
- スキル一覧の行 = プラグイン 1 件（個別 Skill はページ本文に列挙）
- 改善要望は必ず `対象プラグイン` でいずれか 1 プラグインに紐づく

## 反映

```bash
# 差分検知
python3 scripts/sync-notion-schema.py --check

# 適用
python3 scripts/sync-notion-schema.py --apply
```

Notion API キーは macOS Keychain (`security find-generic-password -s notion-api-key -w`) から取得。

## 制約メモ

- Notion API は `status` 型プロパティの作成/更新を許可しない（UI のみ）。本スキーマでは進行管理を `select` で表現。
- `dual_property` relation は片側追加で相手側プロパティが自動生成される。スキーマでは正式名のみを定義し、初回適用時に逆プロパティをリネームする。
- `rollup` は対象 relation が存在しないと作成不可。`sync-notion-schema.py` は relation → rollup の順で適用する。
