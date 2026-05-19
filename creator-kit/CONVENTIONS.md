# Scripting Conventions (Bash vs Python)

本kitおよびプロジェクトにおけるシェルスクリプト言語選択の正典。
「どっちで書くか?」で迷ったらこの文書だけを参照する。

---

## 1. 2層モデル

| Layer | 言語 | 役割 | 例 |
|---|---|---|---|
| L1: Lifecycle / Provisioning | **Bash (.sh)** | ディレクトリ作成、symlink、mv、chmod、git操作、OS標準CLI呼び出し | `install.sh`, `uninstall.sh`, `migrate-from-project.sh` |
| L2: Logic / Tooling | **Python (.py)** | 構造化データ解析、validation、lint、hook、API呼出、secrets管理 | `sink_*.py`, `lint-*.py`, `hook-*.py`, `keychain_helper.py`, `audit_secret_leak.py` |

**原則**: Bash はファイルシステムを動かすだけ。ロジックが要るなら `python3 script.py` を呼ぶ。

---

## 2. 判定フロー (3問)

1. **副作用が「ファイルシステム/プロセス起動」だけか?** → Yes: **Bash**
2. **構造化データ (YAML/JSON/HTTP応答) を解析するか?** → Yes: **Python**
3. **1回限りのセットアップか、繰り返し呼ばれるツールか?** → セットアップ: **Bash** / ツール: **Python**

3問のうち2問以上が Python 寄りなら Python を選ぶ。

---

## 3. 必須骨格

### Bash (.sh)
```bash
#!/usr/bin/env bash
# <one-line purpose>
set -euo pipefail
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
# ... lifecycle operations only ...
```

- `set -euo pipefail` 必須
- 絶対パスを使う (相対パスは `cd` 依存で壊れる)
- ロジックを書きたくなったら Python に出す

### Python (.py)
```python
#!/usr/bin/env python3
"""<one-line purpose>"""
import sys

def main() -> int:
    ...
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- shebang + main() + `sys.exit(code)` 必須
- exit code は `Sink Contract v1.0` に準拠 (0 success / 1 validation / 2 secret / 3 API / 4 fallback)

---

## 4. 過去違反 (すべて解消済み・履歴)

> ⚠️ このセクションは「過去の解消履歴」であり、現在の状態ではない。新規違反を見つけた場合は §6 例外ポリシーに従って記録し、別ファイル `CONVENTIONS-EXCEPTIONS.md` (将来作成) で管理する。

| ファイル | 過去違反 | 解消日 | 解消内容 |
|---|---|---|---|
| `install.sh` / `uninstall.sh` | heredoc Python で YAML 解析 (PyYAML依存) | 2026-05-18 | manifest.yaml → manifest.json 化、heredoc は3行以内の `python3 -c json` に短縮 |
| `resolve_route.py` | `import yaml` で adapter-registry/output-routing 読込 | 2026-05-18 | JSON 化、stdlib `json` のみで完結 |
| `resolve_route.py` | `if __name__ == "__main__": main()` が `sys.exit()` を呼ばず exit code 伝達不能 | 2026-05-18 | `sys.exit(main())` 形式に修正 (§3 必須骨格遵守) |

**現状**: §3 必須骨格・§5 禁則・§6 例外ポリシーすべて違反なし。

---

## 5. 禁則

- **Bash に jq/yq などの非標準依存を入れない** (kit が macOS pristine state で動く前提を破る)
- **Python 内で `subprocess.run([..], shell=True)` を使わない** (引数注入リスク。配列形式必須)
- **Bash heredoc Python ブロックは 5行を超えない** (超えたら Python ファイルに切り出す)
- **Python で `os.system` 禁止** (例外なし。`subprocess` を使う)

---

## 6. 例外ポリシー

**大前提**: macOS デフォルトで入っているもの**だけ**で動かす。新規ライブラリ追加 (pip / brew / npm) は原則禁止。社内配布時のハードルを上げないため。

**統一方針 (Option D)**: 言語は完全統一しない。2層モデル (L1=Bash provisioning / L2=Python stdlib logic) をルールとして固定する。これは「Bash 3.2 で HTTP/JSON を扱う方が壊れやすい」「Python stdlib は `/usr/bin/python3` で必ず入っている」という実利判断に基づく。

**例外を認める条件** (以下すべて満たすこと):

1. **macOSデフォルトのみ**: 例外コードも `/usr/bin/python3` (stdlib) と `/bin/bash` + 標準CLI (`curl`/`security`/`find` 等) だけで動くこと。`import yaml` `import requests` 等は不可。
2. **5行ルール**: Bash内の heredoc Python は5行以内。超えるなら独立 `.py` に切り出す。
3. **記録**: 例外箇所のコード冒頭に `# EXCEPTION: <理由> (<日付>)` コメント必須。レビュー (`run-elegant-review`) で grep して棚卸し可能にする。
4. **クロスプラットフォーム**: Linux/Windows 対応を将来導入する場合、Bash側はOS分岐 (`uname` で判定) で許容。`security` (Keychain) の代替は Python 側で抽象化 (`keychain_helper.py` にOS分岐を集約) し、kit 利用者には CLI 統一を維持する。
5. **承認**: solo_operator_mode のため自己承認。ただし例外を入れる commit には `convention-exception:` プレフィクスを付け、git log で追跡可能にする。

---

## 7. 関連

- `doc/ClaudeCodeスキルの設計書/28-script-execution-model.md` — script実行の責務分離
- `manifest.json` — kit が公開するscript一覧 (Layer/言語別に整理)
- `manifest.json` の `requirements.forbidden_dependencies` — 追加禁止ライブラリの正典リスト
- `scripts/lint-forbidden-deps.py` — forbidden_dependencies の自動検出 (CI/pre-commit用)

---

## 8. scripts 配置の正本ルール (パス二重管理回避)

スクリプト本体の物理配置は以下の階層で正本を一つに固定する。SKILL.md からの参照は **常にプロジェクトルート基準の相対パス**で書く。

| 配置パス | 正本性 | 用途 |
|---|---|---|
| `scripts/*.py` (xl-skills ルート) | **正本 (canonical)** | hook / lint / validate / governance — 全 Skill が共有する横断ツール |
| `creator-kit/scripts/*.py` | **正本 (canonical)** | creator-kit 専用の lifecycle (install/migrate/build-manifest-registration-plan 等) |
| `creator-kit/skills/<skill>/scripts/*.py` | **正本 (canonical)** | その Skill 固有のロジック (例: `run-build-skill/scripts/render-frontmatter.py`) |
| `.claude/skills/<skill>/scripts/*.py` | **派生 (symlink予定)** | Phase 0 完了後、`creator-kit/skills/` への symlink になる。直接編集禁止 |

**SKILL.md 内 bash 記述ルール**:
- xl-skills ルートから起動される前提で **`python3 scripts/foo.py`** または **`python3 creator-kit/scripts/foo.py`** と書く
- skill-local script は **`python3 creator-kit/skills/<skill>/scripts/foo.py`** と書く (`.claude/skills/...` 形式は禁止)
- これにより Phase 0 移行時にもパス参照が破綻しない

**過去の二重管理**: `run-skill-create/SKILL.md` で `scripts/build-manifest-registration-plan.py` と書きつつ実体は `creator-kit/scripts/` にあった等の不整合は、§8 ルールで一意に解消する。
