# skill-intake plugin

skill-creator の前段ヒアリングを **非技術者にも開く** plugin。ユーザーの「スキル作りたい」要望から、本人も言語化できていない真の課題を引き出し、Markdown 正本 + JSON 副本 + Notion ページの 3 成果物を一括生成する。

## 構成

```
plugins/skill-intake/
├── .claude-plugin/plugin.json
├── commands/                  # スラッシュコマンド
│   ├── intake.md              # /intake [topic]
│   ├── intake-publish.md      # /intake-publish <hint>
│   └── intake-status.md       # /intake-status [<hint>]
├── agents/                    # SubAgent (12個, T2 で実装)
├── hooks/                     # secret scrub / keychain verify
│   ├── pre-publish-secret-scrub.sh
│   ├── post-keychain-add.sh
│   └── README.md              # 配線方法 (settings.json 片)
├── scripts/                   # 共有スクリプト (25本, T2 で実装)
└── skills/
    ├── run-skill-intake-aggregator/  # メインスキル (12 phase orchestrator)
    └── wrap-notion-intake-publish/   # Notion 再公開 wrapper
```

## クイックスタート

### 1. macOS Keychain に Notion トークン登録

詳細: [keychain-setup.md](skills/run-skill-intake-aggregator/references/keychain-setup.md)

```bash
security add-generic-password \
  -s notion-api-key \
  -a skill-intake-interviewer \
  -T '' -U
# パスワードプロンプトに ntn_xxx... または secret_xxx... を貼り付け
```

### 2. 動作確認

```bash
chmod +x plugins/skill-intake/hooks/*.sh
bash plugins/skill-intake/hooks/post-keychain-add.sh
# → OK: トークン取得成功 (長さ=N, prefix=ntn_...)
```

### 3. Notion DB 接続確認

提供 DB ID `36607a0cd18c80bf9effc74aa736645c` に PAT / Integration が接続されていることを確認:

```bash
TOKEN=$(security find-generic-password -s notion-api-key -a skill-intake-interviewer -w)
curl -sS https://api.notion.com/v1/databases/36607a0cd18c80bf9effc74aa736645c \
  -H "Authorization: Bearer $TOKEN" \
  -H "Notion-Version: 2022-06-28" | head -20
# 200 OK + DB スキーマが返れば成功
# 403 が返ったら Notion 側の Connections 設定不足
```

### 4. ヒアリング起動

```
/intake デイリーレポート生成スキルを作りたい
```

12 phase が順次実行され、`output/<hint>/` に成果物が生成、Notion DB にページが作成される。

## 既存スキルとの差分

| Skill | 対象 | 図解 | Notion 公開 |
|---|---|---|---|
| `run-skill-elicit` (skill-creator plugin) | 技術者 | ❌ | ❌ |
| **`run-skill-intake-aggregator`** (本 plugin) | **非技術者対応** | ✅ Mermaid 12+SVG 8 | ✅ Keychain × REST API |
| `run-skill-create` (skill-creator plugin) | スキル本体生成 | — | — |

`run-skill-create` から Step 1 を呼ぶ際、ヒアリング対象が非技術者なら本 plugin の `run-skill-intake-aggregator` を起動。

## 実装段階

| 段階 | スコープ | 状態 |
|---|---|---|
| T1 | 骨格 (plugin.json / SKILL.md / commands / hooks / Keychain手順 / DB スキーマ JSON) | ✅ 完了 |
| T2 | scripts 25本 + agents 12本 + references 残り 18本 | ⏳ 未着手 |
| T3 | assets (Mermaid 12 + SVG 8 + samples) | ⏳ 未着手 |
| T4 | P0 lint / 設計評価 / governance / 完了レポート | ⏳ 未着手 |

## ライセンス・所有

owner: team-platform / since: 2026-05-20
