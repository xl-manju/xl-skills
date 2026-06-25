# runtime hook の単独 install ポータビリティ

marketplace から **plugin 単独で install** された先 (cwd 非依存・repo 構造非依存) でも、
hook が import-time にクラッシュせず `exit 0` を維持するための不変条件と機構。

## 不変条件

runtime hook script (`plugins/*/.claude-plugin/plugin.json` の `hooks[]` に配線された
command script) は、**import-time (モジュールトップレベル) に自 plugin root 外のモジュールへ
依存して `raise` してはならない**。

理由: hook は Stop / Edit / Write / Skill 等で毎回 import-time 実行される。単独 install では
plugin 外 (repo-root `scripts/` 等) は存在しない。トップレベルで外部モジュールを動的 import
解決し、不在時に raise すると、その plugin の **全フックが import 時クラッシュ** (exit≠0) し、
ユーザの全 Edit/Write/Stop が壊れる ("exit は常に 0" のフック設計と矛盾)。

## 機構 (二層分離: 再現性は仕組みで担保)

1. **vendoring (実体コピー)**: 必須共有モジュールは正本 (repo-root `scripts/`) から各 plugin の
   `scripts/` へ **byte 完全一致の実体ファイル**でコピーする。symlink は plugin 境界を越えるため
   単独 install (tar 展開) で dangling する。正本は repo-root のまま、plugin 内コピーは移植性ミラー。
   - 例: `scripts/feedback_contract_ssot.py` → `plugins/skill-creator/scripts/feedback_contract_ssot.py`
   - 例: `plugins/skill-creator/scripts/notion_config.py` → `plugins/skill-intake/scripts/notion_config.py`

2. **fail-soft ローダ**: 共有モジュールの解決は次の優先順で行い **絶対に raise しない**。
   - (a) env `CLAUDE_PLUGIN_ROOT/scripts/<module>.py` (Claude Code が hook 実行時に設定)
   - (b) `Path(__file__).parents` の上方探索 (vendored plugin 内コピーを dev/install 双方で発見)
   - (c) 全滅時は **最小 fallback オブジェクトを return** (consumer が実際に使う述語のみ保守的値で提供)。
     vendored コピーが常在するため fallback は実質 dead code (多層防御の最終安全弁)。

3. **queue / 副作用の書込先安全化**: git repo 解決に失敗したとき (git 外 / 単独 install) に
   `os.getcwd()` へ fallback して **無関係なユーザ cwd を汚染しない**。`CLAUDE_PLUGIN_ROOT`
   配下 (self-relative) へ固定するか、書込不能なら silent skip (exit 0 維持・append-only 副作用境界と整合)。

## 機械担保 (lint / CI / byte 一致)

| lint | 検証内容 |
|---|---|
| `scripts/lint-vendored-ssot.py` | vendored コピー = 正本 の byte 一致 (drift で fail-closed)。symlink 回帰も検出。 |
| `scripts/lint-runtime-portability.py` | hook script が import-time に自 plugin 外を fail-closed 依存 (raise) しないことを AST 静的検査。 |

両 lint は Makefile (`make lint` / `make test`) と CI (`creator-kit-ci.yml`) に配線済み。
回帰 pytest (`tests/scripts2/test_root__lint_runtime_portability.py` /
`tests/scripts2/test_root__lint_vendored_ssot.py`) が修正前パターンの FAIL / 修正後の PASS を固定する。

## 検証手順 (単独 install 再現)

plugin ディレクトリのみを repo 外 temp へコピーし (vendored 実体を含める)、空 env で hook を実行し
`exit=0` / Traceback 無しを確認する。

```
cp -R plugins/skill-creator /tmp/standalone/skill-creator
cd /tmp/standalone   # git 外・CLAUDE_PLUGIN_ROOT 未設定
echo '{}' | python3 /tmp/standalone/skill-creator/skills/run-elegant-review/scripts/check-review-trigger.py
echo exit=$?   # => exit=0
```
