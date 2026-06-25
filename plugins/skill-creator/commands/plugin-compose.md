---
description: plugin-composition.yaml を編集または新規生成する。capabilities[] / dependencies を対話的に組み立て、ref-skill-design-rubric の構成評価に通る最小構成を出力する。
argument-hint: "<plugin-name>  例: skill-creator / skill-intake / prompt-creator"
allowed-tools: Read, Write, Edit
name: plugin-compose
kind: command
version: 0.1.0
owner: team-platform
since: 2026-05-24
entrypoint: plugin-compose
---

# /skill-creator:plugin-compose

`$ARGUMENTS` の `<plugin-name>` 配下の `plugin-composition.yaml` を読み、capabilities と dependencies を編集または新規生成する。

## 振る舞い

1. `plugins/$ARGUMENTS/plugin-composition.yaml` の存在を確認。無ければ template から雛形を生成。
2. 配下の `skills/ agents/ hooks/ commands/` を走査し、現状 capabilities[] を実体から再計算。
3. yaml の `capabilities[]` と差分を提示し、追加/削除/更新を確定。
4. `dependencies` (他 plugin への参照) は `.claude-plugin/bundles.json` と整合を取る。
5. 保存後に yaml lint と `ref-skill-design-rubric` の最小チェックを案内。

## 引数

| 引数 | 説明 |
|---|---|
| `plugin-name` | 対象 plugin ディレクトリ名 (必須) |

## 失敗時

- plugin 不在: `plugins/` 配下の一覧を表示
- yaml parse error: 行番号付きで該当箇所を提示し停止
- capabilities 実体不一致: 実体側の rename/move が必要なケースを案内

## 注意

- 本 command は yaml 編集のみ。capability の新規作成は `/skill-creator:capability-build` を併用する。
- bundles.json への登録は別途 manual で行う (依存解決は install-bundle が担う)。
