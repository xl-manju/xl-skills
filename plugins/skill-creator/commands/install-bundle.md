---
description: xl-skills の plugin bundle を 1 コマンドで一括 install する。Claude Code 公式に依存解決機構がないため、bundles.json の定義に従って関連 plugin を順次 install する。
argument-hint: "<bundle-name>  例: xl-skills-full / xl-skills-minimal / xl-skills-intake"
kind: command
---

# /skill-creator:install-bundle

`$ARGUMENTS` で指定された bundle 名に対応する plugin 群を `.claude-plugin/bundles.json` から解決し、それぞれを `/plugin install <name>@xl-skills` で導入する。

## 振る舞い

1. リポジトリルートの `.claude-plugin/bundles.json` を読み、`$ARGUMENTS` と一致する `bundles[].name` を探す。見つからなければ利用可能 bundle 一覧を表示して停止する。
2. 一致 bundle の `plugins[]` を順に `/plugin install <plugin>@xl-skills` で install する。
3. 既に install 済みのものはスキップしたことを報告する。
4. 完了後に `/plugin list` を案内し、欠落 plugin がないかユーザーに確認させる。

## 引数

| 引数 | 説明 |
|---|---|
| `xl-skills-full` | 全 10 plugin (推奨) |
| `xl-skills-minimal` | skill-creator + prompt-creator のみ |
| `xl-skills-intake` | 非エンジニア向け intake パイプライン |

## 失敗時

- bundle 名不一致: bundles.json の `name` 一覧を表示し停止
- 個別 plugin install 失敗: 残りの plugin install は継続し、最後に失敗 plugin を集約して再試行コマンドを提示
- `.claude-plugin/bundles.json` が無い: marketplace ルートに居ない可能性を案内 (`pwd` を実行させる)

## 注意

- Claude Code 公式 plugin manifest には依存宣言フィールドがないため、本コマンドが「依存解決」の代替を担う。
- 新規 plugin を追加する際は `bundles.json` の該当 bundle に必ず登録する。これは `assign-skill-design-evaluator` の rubric で評価される。
