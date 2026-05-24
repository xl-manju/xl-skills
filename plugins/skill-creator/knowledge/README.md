# knowledge/ — skill-creator 自身の蓄積知見ストア (Loop B)

skill-creator が Capability を作成するとき (build-time) に検索して再利用する「蒸留済み知見」。生成スキルに配るのと**同一機構** (`skills/ref-knowledge-loop` 正本 + `skills/run-build-skill/templates/knowledge-skeleton/scripts/`) を skill-creator 自身へ自己適用する dogfooding。

## Loop A と Loop B の関係

| | 場所 | 誰が更新 | いつ使う |
|---|---|---|---|
| Loop A (生成物側) | 生成された各スキルの `knowledge/` | そのスキルの運用 | そのスキルの実行時 |
| Loop B (メタ側) | 本ディレクトリ `plugins/skill-creator/knowledge/` | skill-creator の運用・自己改善 | 次の Capability 作成時 |

両者は `ref-knowledge-loop` の 1 仕様・1 スクリプトを共有する (並行実装を作らない = SSOT)。

## SSOT の役割分担

- `lessons-learned/*.md` … 失敗・落とし穴の**生ログ**が正本。`auto-record-lesson.py` が自動追記。
- `knowledge/` … 作成時に検索する**蒸留済み知見**。`knowledge-lessons-index.json` は lessons-learned 本文をコピーせず `source.file` で参照する (索引のみ)。
- `pattern-feedback.json` / `amplified-patterns.json` … elegant-review の量産パターン蓄積 (別系統)。

## 構成 (Index-Search型)

```
knowledge/
├── knowledge-index.json            # カテゴリ索引 + global_keywords + synonyms + scoring_weights
├── knowledge-build-patterns.json   # ビルド設計パターン・パラダイム (蒸留済み知見)
├── knowledge-lessons-index.json    # lessons-learned への検索用ポインタ
└── usage-log.jsonl                 # §12 活用ログ (作成時の検索結果と採否を追記)
```

## build-time での検索 (Loop B 実体)

検索スクリプトは複製せず、テンプレ正本を `--dir` 指定で直接実行する:

```bash
python3 plugins/skill-creator/skills/run-build-skill/templates/knowledge-skeleton/scripts/search_knowledge.py \
  --dir plugins/skill-creator/knowledge/ --query "<作成中スキルのトピック>" --limit 5
```

`run-skill-elicit` / `run-build-skill` は `brief.consult_build_knowledge=true` (既定) のとき Step 1 でこれを実行し、上位 N 件を設計判断の参考として提示する。採否は `record_usage.py --dir plugins/skill-creator/knowledge/` で `usage-log.jsonl` に記録し、§12 品質改善サイクルを回す。

## エントリ追加・更新

`ref-knowledge-loop/references/knowledge-construction.md` の §4.3 品質ルーブリック (レベル2以上) と §4.4 作成6ステップに従う。必須6フィールド (id / title / intent / background / keywords / source) を満たすこと。25 エントリ超過でサブトピック分割 (§ファイル分割)。
