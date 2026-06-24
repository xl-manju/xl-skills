# MF Kessai Invoice Check Elegant Review

Date: 2026-06-19
Scope: `plugins/mf-kessai-invoice-check/`

## Thought Reset

既存対策の正しさを前提にせず、plugin package を marketplace から任意ディレクトリに install するユーザー視点で再検証した。成果物削除ではなく、仕様・実装・配布契約・実行導線を新規観察した。

## Findings And Fixes

| ID | Finding | Risk | Fix |
|---|---|---|---|
| F1 | `plugin.json` が 36章 `bundle` 契約の `package_mode` / `entry_points` を明示していなかった | marketplace install 時の構成理解と機械検査が弱い | `package_mode: bundle`、skills/agents/hooks/commands/permissions を追加 |
| F2 | `references/package-contract.json` が無かった | PKG-001〜015 の状態を機械可読に追えない | package contract を追加し、pass/skip/not_applicable を明示 |
| F3 | README と responsibility prompt に repo 相対・skill CWD 前提のコマンドが残っていた | 任意 install path でユーザーが迷う | `$CLAUDE_PLUGIN_ROOT` 基準へ統一 |
| F4 | workflow manifest の command が `python3 scripts/...` 前提だった | orchestrator が skill directory 以外から実行すると失敗しうる | manifest command を `$CLAUDE_PLUGIN_ROOT/skills/...` へ変更 |
| F5 | install smoke 契約上の実行可能ビットがテストで固定されていなかった | ユーザーに手動 chmod を要求する退行が起きる | script/hook の executable bit を設定しテスト追加 |
| F6 | 可搬性・manifest 契約の回帰テストが不足していた | 仕様適合が人手レビュー頼みになる | `tests/test_plugin_contract.py` を追加 |

## 30 Thinking Methods Coverage

| # | Thinking method | Applied conclusion |
|---:|---|---|
| 1 | 批判的思考 | 「動く」ではなく install 契約と任意 path で疑った |
| 2 | 演繹思考 | 36章 bundle 必須キーから `plugin.json` 不足を導出 |
| 3 | 帰納的思考 | README/prompts の複数裸相対パスから可搬性リスクを一般化 |
| 4 | アブダクション | install 失敗の最善説明を path/cwd 前提の残存と推定 |
| 5 | 垂直思考 | 表層 README ではなく manifest/prompt/test まで掘った |
| 6 | 要素分解 | skill/agent/hook/lib/config/test/manifest に分解 |
| 7 | MECE | 配布契約・実行導線・安全性・検査自動化に分類 |
| 8 | 2軸思考 | 人間向け導線と機械向け契約の2軸で評価 |
| 9 | プロセス思考 | collect→verify→finalize→sink の順序と fail-closed を確認 |
| 10 | メタ思考 | SKILL 散文ではなく contract/test に固定する方針を採用 |
| 11 | 抽象化思考 | 「path 非依存」を `$CLAUDE_PLUGIN_ROOT` ルールへ抽象化 |
| 12 | ダブル・ループ思考 | repo 直下実行を前提にする運用前提自体を疑った |
| 13 | ブレインストーミング | manifest、README、prompt、workflow、test の改善案を列挙 |
| 14 | 水平思考 | 他 plugin の manifest 形式も比較対象にした |
| 15 | 逆説思考 | 「install 後に CWD が違うなら何が壊れるか」で検査 |
| 16 | 類推思考 | contract-generator/prompt-creator の manifest metadata を参考化 |
| 17 | if思考 | `$CLAUDE_PLUGIN_ROOT` 未使用、別 CWD、未 chmod の場合を想定 |
| 18 | 素人思考 | README の手順だけ見た導入者が迷う箇所を確認 |
| 19 | システム思考 | Plugin manifest、hook、subagent、Notion sink の連動を確認 |
| 20 | 因果関係分析 | 裸相対 path → 実行失敗 → verify/sink 未完了の因果を特定 |
| 21 | 因果ループ | 検査不足→退行→手動修正のループをテストで遮断 |
| 22 | トレードオン思考 | 大改造せず、契約明示と可搬性修正で安全性も上げた |
| 23 | プラスサム思考 | ユーザー導線と validator の両方を改善 |
| 24 | 価値提案思考 | 月次発行漏れ検知という価値を install 直後に使える状態へ寄せた |
| 25 | 戦略的思考 | 36章 PKG 契約に合わせ、将来 smoke/CI 接続しやすくした |
| 26 | why思考 | なぜ path 問題が起きるかを CWD/install 位置前提まで遡った |
| 27 | 改善思考 | 仕様不足を manifest/test/report に反映 |
| 28 | 仮説思考 | 「裸相対 path が主要リスク」という仮説を rg とテストで検証 |
| 29 | 論点思考 | 真の論点を API ロジックでなく marketplace install 可搬性に設定 |
| 30 | KJ法 | findings を F1〜F6 にグルーピング |

## Four Conditions

| Condition | Result | Evidence |
|---|---|---|
| 矛盾なし | PASS | `plugin.json` / workflow / prompt command を `$CLAUDE_PLUGIN_ROOT` に統一 |
| 漏れなし | PASS | skills 3、agent 1、hook 1、commands、permissions、package contract を manifest 化 |
| 整合性あり | PASS | JSON parse、pytest、plugin completeness が PASS |
| 依存関係整合 | PASS | `validate-plugin-completeness.py` で hook/asset/bundle 整合 OK |

## Verification

- `pytest -q plugins/mf-kessai-invoice-check/tests` -> 26 passed
- `python3 scripts/validate-plugin-completeness.py` -> OK: 12 plugin(s) complete
- `python3 -m json.tool` for plugin manifest, package contract, workflow manifest -> OK
