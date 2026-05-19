# 34a 章 settings.json マージ仕様

最終更新: 2026-05-19

## §1 目的

`plugins/<name>/.claude-plugin/plugin.json` と `plugins/<name>/{hooks,settings}/` から、開発用 `.claude/settings.json` の plugin 由来設定区間を決定的に再生成するための正本仕様を定義する。

本章は 34章の plugin 物理レイアウトを補完する。CLI 引数の詳細は `doc/task/04-settings-merge-cli-specification.md`、実装は `doc/task/07-build-claude-settings-implementation.md` が従う。

## §2 三層モデル参照と正本境界

34章で定義した三層モデルは、Layer1 `plugin.json`、Layer2 `hooks/` と `settings/`、Layer3 `.claude/settings.json` の順に派生する。本章は Layer3 を自動生成するときの不変条件を固定する。

| 領域 | 正本 |
|---|---|
| plugin 移行 Phase gate | `34-plugin-governance-roadmap.md` |
| settings merge 不変条件 | 本章 |
| CLI 契約 | `doc/task/04-settings-merge-cli-specification.md` |
| 実装検証 | `doc/task/07-build-claude-settings-implementation.md` |

## §3 対象データと非対象データ

plugin 由来で `.claude/settings.json` にマージする対象は、現時点では下記に限定する。

| 種別 | 入力候補 | 出力先 | マージ規則 |
|---|---|---|---|
| hooks | `plugin.json` inline hooks、`hooks/hooks.json`、`hooks/*.json` | `hooks` | event/matcher/command 単位で正規化し、衝突検出後に公式 hook 構造へ出力 |
| permissions.deny | `settings/permissions.json` または plugin manifest の permissions 宣言 | `permissions.deny` | 完全一致は重複排除、同一対象の allow/ask/deny 競合は fail |
| permissions.ask | `settings/permissions.json` または plugin manifest の permissions 宣言 | `permissions.ask` | 完全一致は重複排除、deny と衝突したら deny 優先ではなく fail |

`skills/`、`agents/`、`commands/` の生成は `.claude/settings.json` ではなく `.claude/{skills,agents,commands}/` の symlink 派生で扱う。したがって、同名 skill 等の衝突は本章の settings merge だけでなく、`doc/task/03-symlink-build-specification.md` の namespace preflight で必ず検出する。

## §4 グローバル名前空間 preflight

settings merge を実行する前に、plugin 群全体を走査して以下の名前空間を作る。

| 名前空間 | キー | 衝突時の扱い |
|---|---|---|
| skill | `skills/<dir-name>` と `SKILL.md` の `name` | 同名は exit 2。dev短名 symlinkでは先勝ち禁止 |
| agent | `agents/<file-name>` | 同名は exit 2 |
| command | `commands/<file-name>` | 同名は exit 2 |
| hook | `event + matcher + command` | 異なる plugin 由来の完全一致は exit 2 |
| permission | `scope + rule` | 完全一致は dedupe。異なる decision 間の競合は exit 2 |
| plugin | `.claude-plugin/plugin.json` の `name` | 同名 plugin は exit 3 |

公式 plugin 実行時の namespaced invocation と、開発用 `.claude/skills/<short-name>` symlink は別物として扱う。dev短名 symlink では同名を許可しない。許可したい場合は、plugin 側で skill 名または directory 名を変更する。

## §5 settings JSON 構造

生成後の `.claude/settings.json` は、最低限下記の構造を満たす。

```json
{
  "_build_claude_settings": {
    "managed_hooks": []
  },
  "permissions": {
    "deny": [],
    "ask": []
  },
  "hooks": {
    "PreToolUse": []
  }
}
```

構造検証ルール:

- `permissions` は object。`deny` と `ask` は存在する場合 array。
- `hooks` は object。key は公式 hook event 名のみ。hook event 値は array。
- hook entry は object。`hooks` field は array。
- hook command entry は object。`type` と `command` を必須とし、`type` は `command` のみ許可。
- 生成対象の管理情報は top-level `_build_claude_settings` にのみ出力し、`hooks` 配下には番兵キーや unknown hook event を出力しない。
- user 管理値の unknown top-level key は保存するが、生成管理メタデータには混ぜない。

## §6 管理メタデータ構文

JSON コメントは使えない。また、Claude Code hooks は `hooks` オブジェクト直下の key を hook event として扱うため、`hooks` 配下に `_generated_section_start` などの番兵キーを置いてはならない。

公式 plugin hooks は plugin 内の `hooks/hooks.json` または `plugin.json` inline のどちらでも入力にできる。開発用 `.claude/settings.json` への派生生成では、実 hook 定義は公式構造のまま `hooks` 配下へ出力し、生成管理情報は top-level `_build_claude_settings` に分離する。

```bnf
managed-metadata    ::= "_build_claude_settings": managed-object
managed-object      ::= "managed_hooks": managed-hook*, "managed_permissions": managed-permission*
managed-hook        ::= {"event": hook-event, "matcher": string-or-null, "command": string, "from_plugin": string}
managed-permission  ::= {"scope": permission-scope, "decision": permission-decision, "rule": string, "from_plugin": string}
hook-event          ::= "PreToolUse" | "PostToolUse" | "SubagentStop" | "TaskCompleted" | "TaskCreated" | "FileChanged" | "PreCompact" | "PostCompact"
permission-scope    ::= "permissions.deny" | "permissions.ask"
permission-decision ::= "deny" | "ask"
```

`managed_hooks` は前回生成した hook entry を識別するための台帳であり、次回実行時はこの normalized triple (`event`, `matcher`, `command`) に一致する既存 entry だけを置換対象にする。`managed_hooks` に載っていない user 管理 hook は保存する。

## §7 マージアルゴリズム

```text
load target .claude/settings.json as raw text and JSON AST
run global namespace preflight for plugins, skills, agents, commands, hooks, permissions
extract previous managed metadata from _build_claude_settings
load plugins sorted by plugin name
for each plugin:
  load .claude-plugin/plugin.json
  load hooks/hooks.json and hooks/*.json if present
  load settings/permissions.json if present
  normalize every hook as event, matcher, command, from_plugin
  normalize every permission as scope, decision, rule, from_plugin
detect duplicate or conflicting namespace entries
if conflict exists:
  fail without writing target
render generated section in deterministic order
remove previously managed hooks/permissions by metadata, then merge user-managed values + newly generated values
verify INV-1 through INV-12
write by tempfile + rename only after every invariant passes
```

## §8 不変条件

## INV-1 user 管理値保存

`_build_claude_settings` の `managed_hooks` / `managed_permissions` に載っていない既存設定は保存しなければならない。JSON 全体を parse/serialize する実装では byte 等価ではなく、JSON 値としての意味的等価を検査対象にする。

機械検証: 管理メタデータに載っていない user 管理値を正規化 JSON として抽出し、SHA256 を実行前後で比較する。

## INV-2 決定的生成

入力 plugin 群と target が同じなら、生成される hook / permission / 管理メタデータは常に同じでなければならない。

機械検証: 固定 fixture に対する golden JSON を比較する。

## INV-3 冪等性

同じ入力で CLI を2回実行した後、`--check` は差分なしで exit 0 を返さなければならない。

機械検証: 実行、再実行、`--check` の3段階テストを行う。

## INV-4 plugin 順序

複数 plugin の hook は plugin name の辞書順、同一 plugin 内では event、matcher、command の順で安定整列する。

機械検証: 入力ディレクトリ順を入れ替えた fixture で出力が同一であることを確認する。

## INV-5 衝突 ERROR

異なる plugin が同一 event、matcher、command を提供した場合、silent merge せず invariant violation として失敗する。

機械検証: 衝突 fixture で exit 2 と conflict report を確認する。

## INV-6 未知キー保存

`.claude/settings.json` の未知トップレベルキーと、既知キー内の user 管理値は削除してはならない。

機械検証: 未知キー fixture の実行前後 SHA256 または AST 等価を比較する。

## INV-7 JSON 正規化

生成 hook / permission / 管理メタデータは UTF-8、indent 2、末尾改行あり、schema 順で出力する。user 管理値にはこの正規化を強制しない。

機械検証: 生成 hook / permission / 管理メタデータだけを抽出し、formatter fixture と比較する。

## INV-8 原子的書き込み

すべての検証が PASS するまで target を置換してはならない。書き込みは同一ディレクトリの tempfile に出力し、rename で置換する。

機械検証: 書き込み失敗を注入し、target の SHA256 が実行前と一致することを確認する。

## INV-9 グローバル名前空間一意性

plugin、skill、agent、command の dev短名名前空間は一意でなければならない。同名を検出した場合、`.claude/settings.json` も `.claude/skills` 等も更新してはならない。

機械検証: 同名 skill fixture で exit 2、target SHA256 不変を確認する。

## INV-10 settings 構造検証

生成後の `.claude/settings.json` は、本章「settings JSON 構造」の型制約を満たさなければならない。

機械検証: Python stdlib の JSON parse 後、必須 key、型、hook command entry を検査する。

## INV-11 permissions マージ安全性

permissions は完全一致のみ dedupe する。deny と ask のように decision が異なる同一 rule は自動優先順位で解決せず、exit 2 とする。

機械検証: permissions conflict fixture で exit 2、完全一致 fixture で dedupe 件数が report に出ることを確認する。

## INV-12 plan 完全性

`--dry-run --json` の plan は、settings だけでなく skill/agent/command 名前空間 preflight の結果も含めなければならない。

機械検証: plan JSON に `namespace`, `settings`, `conflicts`, `invariants_checked` が存在し、INV-1〜INV-12 を列挙することを確認する。

## §9 衝突検出

### hook 衝突検出

衝突キーは `event + "\0" + matcher + "\0" + command` とする。`matcher` が省略された hook は空文字として扱う。

```text
seen = {}
for hook in normalized_hooks:
  key = (hook.event, hook.matcher or "", hook.command)
  if key in seen and seen[key].from_plugin != hook.from_plugin:
    conflicts.append({key, plugins: [seen[key].from_plugin, hook.from_plugin]})
  else:
    seen[key] = hook
if conflicts:
  return exit 2 without writing
```

### permissions 衝突検出

```text
seen = {}
for permission in normalized_permissions:
  key = (permission.scope, permission.rule)
  if key in seen and seen[key].decision != permission.decision:
    conflicts.append({key, decisions: [seen[key].decision, permission.decision]})
  else:
    seen[key] = permission
dedupe exact duplicates
if conflicts:
  return exit 2 without writing
```

## §10 例

### 例 1: 単一 plugin

入力:

```json
{
  "name": "skill-creator",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PROJECT_DIR}/plugins/skill-creator/scripts/hook-validate-skill-md.py"
          }
        ]
      }
    ]
  }
}
```

期待出力の生成結果:

```json
{
  "_build_claude_settings": {
    "managed_hooks": [
      {
        "event": "PreToolUse",
        "matcher": "Write|Edit",
        "command": "python3 ${CLAUDE_PROJECT_DIR}/plugins/skill-creator/scripts/hook-validate-skill-md.py",
        "from_plugin": "skill-creator"
      }
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PROJECT_DIR}/plugins/skill-creator/scripts/hook-validate-skill-md.py"
          }
        ]
      }
    ]
  }
}
```

### 例 2: 複数 plugin マージ

`alpha` と `skill-creator` が異なる matcher または command を提供する場合は、plugin name 辞書順で生成 hook 配列に並べる。

### 例 3: 衝突 ERROR

`alpha` と `skill-creator` が同一 `PreToolUse`、同一 `Write|Edit`、同一 command を提供する場合は exit 2。target は更新しない。

## §11 機械検証手段

| 条件 | 検証 |
|---|---|
| 矛盾なし | 本章、34章、task 04/07 の正本境界を照合する |
| 漏れなし | INV-1〜INV-12 の fixture を1件以上ずつ持つ |
| 整合性あり | CLI plan JSON に `invariants_checked` を含め、全 INV と namespace preflight 結果を列挙する |
| 依存関係整合 | 02 → 04 → 07 → 08 の順序を守り、08 は 34章 Phase 1→2 gate PASS 後に実行する |

## §12 CLI 契約への引き継ぎ

`scripts/build-claude-settings.py` は少なくとも `--plugins-dir`、`--target`、`--dry-run`、`--check`、`--print-user-section-hash`、`--json` を提供する。終了コードは `0=success`、`1=drift`、`2=invariant violation / namespace conflict`、`3=invalid input / invalid plugin layout` とする。

この章と CLI 仕様が競合した場合、INV の意味は本章、引数名と出力スキーマは task 04 を優先する。
