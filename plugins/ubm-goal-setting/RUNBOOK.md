# ubm-goal-setting Runbook

## Purpose

この runbook は、`ubm-goal-setting` plugin の個人利用運用で確認すべき入口、環境変数、保護境界、検証コマンドをまとめる。

## Entry Points

- `/ubm-goal-setting [weekly|monthly|bimonthly]`: 目標設定・振り返り対話を生成し、`validate-goal-output.py` で保存前検証する。
- `/ubm-knowledge-sync [--all] [--since YYYY-MM-DD] [--dry-run]`: L2 vault source の差分を検知し、knowledge JSON を同期する。
- `/ubm-youtube-ingest [--url URL | --backfill | --sync] [--source SOURCE] [--dry-run]` (v0.2.0): 北原さん YouTube を 3 モード（URL 単発 / 厳格全量 / scheduler 無人差分）で手動起動・再実行・dry-run する。手動 sync は scheduler one-shot と同一 cursor / idempotency key（`video_id`）を共有する。モード（`--url`/`--backfill`/`--sync`）は相互排他。
- `/ubm-consult "[相談内容]"` (v0.2.0): 具体解を処方せず考え方（思考フレーム）を提示するコーチング型相談。`run-ubm-consult` スキルは `disable-model-invocation: true` のため発話では自動起動せず、本コマンドが唯一の入口。目標設定そのものは `/ubm-goal-setting`（`run-ubm-goal-setting`）へ委譲する。

## Environment

- `UBM_VAULT_ROOT`: L2 raw vault source と Daily.md embed 更新先の root。未設定または未接続でも L1 curated knowledge は plugin 同梱 seed から読める。
- `CLAUDE_PLUGIN_ROOT`: hook と skill scripts の self-relative 解決に使う plugin root。

## Write Protection

`hooks/ubm-write-path-guard.py` は `UBM_VAULT_ROOT` 配下の Write/Edit/MultiEdit だけを検査する。

許可する vault write:

- `05_Project/UBM/目標設定/` 配下の目標設定ファイル保存
- `02_Configs/Templates/Daily.md` の embed 参照更新

保護対象外:

- vault 外の plugin 同梱 `knowledge/*.json`
- `UBM_VAULT_ROOT` 未設定時の任意 path
- Read など非 write tool

## Verification

```bash
python3 -m pytest plugins/ubm-goal-setting/tests -q
python3 plugins/ubm-goal-setting/skills/run-ubm-knowledge-sync/scripts/check-knowledge-split.py --dir plugins/ubm-goal-setting/knowledge
python3 -m json.tool plugins/ubm-goal-setting/.claude-plugin/plugin.json >/dev/null
python3 -m json.tool plugins/ubm-goal-setting/EVALS.json >/dev/null
```

## YouTube Sync（scheduler / 冪等 one-shot）— v0.2.0

無人の定期取込は、手動コマンド（`/ubm-youtube-ingest`）と**同一の one-shot**（`skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py`）を host scheduler が呼ぶことで実現する（daemon 常駐でなく lease 付き one-shot の portable 設計）。手動 sync と scheduler は同じ cursor / idempotency key（`video_id`）を共有し、別系統の状態を作らない。

one-shot の実行（repo root から）:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json \
  --channel <handle> \
  --source-out "$UBM_VAULT_ROOT/05_Project/UBM/YouTube" \
  --mode sync --max-retries 3 --lease-ttl 900
```

- **provider**: `--provider` の既定は `fixture`（受入テスト用）。具体 YouTube provider は運用時に late-bind する設計で、fixture 経路（`--provider fixture --fixture <file>`）で冪等性を検証する。
- **正規化ソースの配置**: `--source-out` は `detect-knowledge-updates.py` が `source_type=youtube` として検知できる vault 配下（`05_Project/UBM/` 配下）にする。one-shot は provenance を保った lossless 保存に徹し、意味抽出（C08→C06）は下流 R3 が担う。
- **書込境界**: one-shot の write-scope は `--registry` と `--source-out` 配下のみ。`--dry-run` は registry 初期化も含め書込 0。plugin 同梱 `knowledge/*.json` / registry は vault 外ゆえ `ubm-write-path-guard` の対象外（vault 側 asset 書込のみ hook が検査する）。

cron 設定例（毎時 05 分に差分同期・repo root へ cd）:

```cron
5 * * * * cd /path/to/xl-skills && UBM_VAULT_ROOT="$HOME/dev/dev/ObsidianMemo" python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/run-youtube-sync-oneshot.py --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json --channel <handle> --source-out "$UBM_VAULT_ROOT/05_Project/UBM/YouTube" --mode sync >> "$HOME/.ubm-youtube-sync.log" 2>&1
```

### 失敗時の確認（retry / alert / lease）

one-shot は stdout に sync report（JSON・正本形式は `skills/run-ubm-youtube-ingest/references/sync-report-format.md`）を出す。scheduler ログでは以下を確認する:

- **temporary_failure**: `alerts` に `[temporary_failure] <video_id> (attempt N)`。次回 run で自動 retry され、復旧すると `ingested` に計上される（`attempts` が増える）。`--max-retries`（既定 3）超過は `[retry_exhausted]`。
- **quota / auth**: `stopped_reason` が `quota` / `auth`。graceful stop（exit 0）で scheduler は次 cadence で再開する。`alerts` に `[quota]` / `[auth]`。
- **lease**: scheduler 二重発火時、未失効 lease を持つ run が居れば `stopped_reason=lease_held` の no-op（exit 0）。`--lease-ttl`（既定 900 秒）を運用 cadence に合わせる。
- **冪等性**: 同一動画は `already_ingested` に写像され二度 ingest されない（idempotency key=`video_id`）。二回目 run は `ingested=0`。

### 完全性ゲート（--backfill）

`--backfill` の全量性は authoritative snapshot（`--video-list`）を分母に固定して機械判定する:

```bash
python3 plugins/ubm-goal-setting/skills/run-ubm-youtube-ingest/scripts/check-youtube-backfill-completeness.py \
  --channels <handle> \
  --video-list <snapshot.json> \
  --registry plugins/ubm-goal-setting/knowledge/youtube-registry.json
```

`FULL_BACKFILL_PASS` は `ingested==discovered_total` かつ `temporary_failure==0` かつ `unapproved_unavailable==0`（exit 0）。除外による分母縮小・重複 ID・pagination 欠落・waiver 参照欠落は exit 1、usage/入力不正は exit 2。

## Graph Verification（knowledge / harness artifact）— v0.2.0

knowledge 依存グラフの決定論再生成 + 検証:

```bash
python3 plugins/ubm-goal-setting/scripts/validate-knowledge-graph.py \
  --knowledge-dir plugins/ubm-goal-setting/knowledge \
  --graph-out plugins/ubm-goal-setting/knowledge/knowledge-graph.json
```

参照整合・self-loop 禁止・`depends_on` の DAG 非循環・evidence≥1・confidence 0..1・review_status 必須を検査（exit 0=OK / 1=違反 / 2=usage）。PASS 時のみ `knowledge-graph.json` を書く。

harness artifact graph の index 生成と read-only consult:

```bash
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json

python3 plugins/ubm-goal-setting/scripts/consult-harness-artifact-graph.py \
  --topic "youtube ingest 全量性" \
  --knowledge-graph plugins/ubm-goal-setting/knowledge/knowledge-graph.json \
  --harness-artifact-graph plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json \
  --query-type local --depth 2
```

consult は zero-hit も正常終了（exit 0）。`--knowledge-graph` は必須、`--harness-artifact-graph` は任意。**harness graph だけ不在なら `--harness-artifact-graph` を省いて knowledge 単独 consult に落ち**、knowledge graph も不在のときだけ `run-ubm-consult` / `info-collector` は `router.json` デュアルパスへ fallback する（fallback 契約の正本＝`references/graph-consult-fallback-contract.md`）。

### harness artifact graph の再生成（定常手順・鮮度 SLA）

`harness-artifact-graph.json`（C05）は「これから作る計画」と「実成果物」を突合した index であり、**plugin を build/レビューして実成果物（task-state / route-report / build-trace / 実在 build_target）が変わるたびに陳腐化する**。次のタイミングで `index-harness-artifact-graph.py` を再実行して再生成する:

- **build / レビュー完了後**（component の追加・state 遷移 planned→built→verified が起きたら必ず）。
- **consult 前に鮮度確認**: 生成から時間が経っている場合は再生成してから consult する。目安の鮮度 SLA は **7 日**（それより古い index は `state`/`stale_reasons` が実態とずれている可能性があるため再生成推奨）。
- 再生成しない間は harness graph を **省略して knowledge 単独 consult** しても良い（誤同定した stale index を引くより安全）。C06 `knowledge-graph.json` は knowledge 実データが変わったとき再生成する。

```bash
# build/レビュー後の再生成（再掲）
python3 plugins/ubm-goal-setting/scripts/index-harness-artifact-graph.py \
  --plan-glob "plugin-plans/ubm-goal-setting/*" \
  --plugin-root plugins/ubm-goal-setting \
  --out plugins/ubm-goal-setting/knowledge/harness-artifact-graph.json
```

## Acceptance Evidence

- C16: 週報/月報/期報を生成し、`validate-goal-output.py --type weekly|monthly|bimonthly` が PASS すること。
- C17: 既知の更新済み source で NEW/MODIFIED を検知し、knowledge-extractor が6カテゴリ分類と `router.json` / `registry.json` 同期を完了すること。
- C04: `UBM_VAULT_ROOT` 配下の許可外 path への Write/Edit/MultiEdit が exit 2 で阻止されること。

## Recovery

- `UBM_VAULT_ROOT` が未接続の場合、knowledge sync は 0件レポートとして正常終了する。vault を接続して再実行する。
- `check-knowledge-split.py` が 500行超過を検知した場合、25エントリ基準でサブテーマを設計し、`{category}-{subtopic}.json` へ分割する。
- 目標設定出力が validate に失敗した場合、未展開 `{{...}}`、全角数字、差分の `+/-`、やらないこと3項目、種別別必須見出しを優先して直す。
- (v0.2.0) `youtube-registry.json` 未存在時、one-shot は required-primary + pending 第2source で自動初期化する（`--dry-run` は初期化も書込まない）。破損 registry は上書きしない（exit 1）ため、破損時はバックアップから復旧して再実行する。
- (v0.2.0) `--backfill` の完全性ゲートが exit 1 の場合、stderr の pending / temporary_failure / unapproved_unavailable / waiver 欠落 / 重複 ID / pagination 欠落 の video ID を確認し、除外で分母を縮めず取得を再試行する。承認済み除外は `waiver_ref` を付ける。
- (v0.2.0) `validate-knowledge-graph.py` が exit 1 の場合、stderr の violation（dangling / self-loop / evidence 欠落 / confidence 範囲外 / review_status 欠落 / cycle）を確認し、C08（`knowledge-relation-extractor`）の辺 handover を修正して再生成する。`related` は無方向連想（cycle 対象外）である点に注意する。
