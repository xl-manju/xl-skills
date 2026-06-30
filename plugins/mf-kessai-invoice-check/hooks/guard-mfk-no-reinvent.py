#!/usr/bin/env python3
"""PreToolUse hook: 本plugin の照合/判定ロジックの『再発明』と『TODO(human) 丸投げ』を機械遮断する。

背景 (再発防止の恒久レバレッジ = LP-β):
  正規スキル (run-mf-invoice-reconcile) が起動されず、Claude が請求確認シート × MF掛け払い
  照合を自前スクリプトで再実装し、中核判定 (classify 相当) を `TODO(human)` で人間へ丸投げした
  事故が起きた。README/SKILL の prose 指示 (「自作するな」) は出力スタイル (Learning 等) の
  TODO(human) 規約に上書きされうるため、保証要件はプロンプトでなく機械層 (PreToolUse exit 2)
  へ昇格する。第1層 guard-mfk-readonly.py が MF API 変更系 (Bash) を遮断するのと対称に、本 hook は
  Write/Edit 経路の『迂回 (再発明)』を遮断する第3の防壁。

遮断する生成コンテンツ (tool: Write / Edit / MultiEdit / Bash):
  R1 anti-TODO(human): MF掛け払い照合ドメインの文脈で `TODO(human)` を**コードに**書き込む
     → exit 2。判定は実装済み (lib/mfk_reconcile.py)。人間に判定を書かせない。
  R2 anti-reinvention: 正本 (lib/mfk_reconcile.py / scripts/reconcile_invoices.py) 以外の
     新規ファイルへ、請求確認シート × MF 照合を再実装する関数定義
     (`def classify` / `def reconcile` / `def detect_orphans` / `def build_mf_index` 等) を
     書き込む → exit 2。/run-mf-invoice-reconcile と lib/mfk_reconcile を使う。
  R3 anti-Bash bypass: Bash の heredoc / tee / redirection / Python write 経路で上記を
     ファイル生成する迂回も同じく遮断する。単なる echo や grep 等の read-only コマンドは
     遮断しない。

精度方針 (誤遮断を避ける):
  - **ドメイン信号が無いコンテンツには一切発火しない** (他プロジェクトの正当な TODO(human)/
    classify を誤遮断しない)。本 plugin 固有のドメイン語 (請求確認シート / mfk_reconcile /
    掛け払い + 照合 / 発行漏れ 等) を含むか、本 plugin 配下のパス宛てのときだけ判定する。
  - **ドキュメント (.md) は対象外**: README/SKILL が反パターンを文章で説明・引用するのは正当。
  - **テストコード (/tests/) は対象外**: 本 hook 自身の回帰テストが TODO(human) 文字列や
    classify 定義を fixture として持つため。
  - **allowlist は R2 (再実装) にのみ適用**: 正本 (mfk_reconcile.py / reconcile_invoices.py)
    への `def classify/reconcile` 等の保守編集を妨げない。ただし **R1 (anti-TODO(human)) は
    正本を含む全ドメインファイルへ意図的に適用**する (判定丸投げは正本上でも禁止する)。

射程限界 (over-promise しないための正直な明記 — guard-mfk-readonly と同じ規律):
  本 hook は「ドメイン信号 (_DOMAIN_RE) を含むか本 plugin 配下のパス宛て」のときだけ発火する
  **摩擦増加層であって、絶対保証ではない**。信号語を避けた言い換えで plugin 外パスへ
  `def classify` を書く等の迂回は構造上捕捉できない (偽陰性)。readonly 側は `mfk_api.py` が
  POST 関数を実装しない**構造的 backstop** で保証を成立させられるが、「照合関数を書けない」
  ように任意コード生成を構造的に不能化することはできないため、本 hook に等価な backstop は
  原理的に存在しない。したがって**第一防壁は柱1 (run-mf-invoice-reconcile の自然文自動起動)
  による『再発明する動機の除去』**であり、本 hook はそれを補う第二防壁 (動機が残った場合の
  書込時 fail-safe) と位置づける。malformed payload 時は exit 0 (fail-open) で通常操作を妨げない。
"""
import json
import os
import re
import sys

# 照合/判定を実装してよい正本ファイル (これ以外への照合関数定義は再発明とみなす)。
SANCTIONED_BASENAMES = {"mfk_reconcile.py", "reconcile_invoices.py"}

# 本 plugin 固有の照合ドメイン信号。これを含まないコンテンツ/パスには発火しない。
_DOMAIN_RE = re.compile(
    r"請求確認シート|mfk_reconcile|reconcile_invoices|掛け払い|mfkessai"
    r"|発行漏れ|verdict-mapping|verdict_mapping|billings/qualified|sheet_to_master",
    re.IGNORECASE,
)

# 照合/判定エンジンの再実装シグネチャ (正本のみが持つべき関数名)。
_REINVENT_DEF_RE = re.compile(
    r"def\s+(classify|reconcile|detect_orphans|build_mf_index|judge_label|sheet_label)\s*\(",
    re.IGNORECASE,
)

_TODO_HUMAN_RE = re.compile(r"TODO\(human\)", re.IGNORECASE)

_PLUGIN_DIR_MARK = "mf-kessai-invoice-check"


def _content_of(tool, ti):
    """Write/Edit/MultiEdit の『新たに書き込まれるテキスト』を抽出する。"""
    if tool == "Write":
        return ti.get("content", "") or ""
    if tool == "Edit":
        return ti.get("new_string", "") or ""
    if tool == "MultiEdit":
        return "\n".join(
            (e or {}).get("new_string", "") or "" for e in (ti.get("edits") or [])
        )
    if tool == "Bash":
        return ti.get("command", "") or ""
    return ""


def _bash_write_targets(command):
    """Bash command から明示的な書き込み先候補を粗く抽出する。

    shell 完全解析ではなく、PreToolUse での安全側検知に必要な heredoc/redirection/tee の
    主要形を拾う。抽出できない Python write 等は空配列のまま _bash_has_write_intent で扱う。
    """
    targets = []
    # cat <<'PY' > path.py / echo x >> path.py / command 2>err など。
    for m in re.finditer(r"(?:^|[\s])(?:[0-9]*>>?|&>)\s*(['\"]?)([^\s'\";|&]+)\1", command):
        targets.append(m.group(2))
    # tee path.py / tee -a path.py
    for m in re.finditer(r"(?:^|[\s])tee(?:\s+-a)?\s+(['\"]?)([^\s'\";|&]+)\1", command):
        targets.append(m.group(2))
    return targets


def _bash_has_write_intent(command):
    """Bash がファイル生成/更新を意図しているか。

    単なる `echo TODO(human)` や `rg def classify` は許可し、heredoc/tee/redirection/
    Python の write_text/open(...,'w') 系だけを遮断対象にする。
    """
    lowered = command.lower()
    if _bash_write_targets(command):
        return True
    write_patterns = (
        r"\.write_text\s*\(",
        r"\.write_bytes\s*\(",
        r"\bopen\s*\([^)]*,\s*['\"][wa+]",
        r"\.write\s*\(",
    )
    return any(re.search(p, lowered) for p in write_patterns)


def _is_exempt_path(path):
    """ドキュメント (.md) とテスト (/tests/) と hook 自身は対象外 (誤遮断回避)。"""
    p = path.replace("\\", "/")
    if p.lower().endswith((".md", ".mdx", ".markdown")):
        return True
    if "/tests/" in p or p.endswith("/tests"):
        return True
    if os.path.basename(p) == "guard-mfk-no-reinvent.py":
        return True
    return False


def _in_domain(path, content):
    """本 plugin の照合ドメインに属するか (パス or コンテンツ信号)。"""
    p = path.replace("\\", "/")
    return _PLUGIN_DIR_MARK in p or bool(_DOMAIN_RE.search(content))


def evaluate(tool, ti):
    """遮断すべきか判定する。遮断時は (True, message)、許可時は (False, "")。"""
    if tool not in ("Write", "Edit", "MultiEdit", "Bash"):
        return False, ""
    path = ti.get("file_path", "") or ""
    content = _content_of(tool, ti)
    if not content:
        return False, ""
    if tool == "Bash":
        if not _bash_has_write_intent(content):
            return False, ""
        targets = _bash_write_targets(content)
        if targets and all(_is_exempt_path(t) for t in targets):
            return False, ""
        if targets and all(os.path.basename(t.replace("\\", "/")) in SANCTIONED_BASENAMES for t in targets):
            return False, ""
    elif _is_exempt_path(path):
        return False, ""
    if not _in_domain(path, content):
        return False, ""

    # R1: ドメイン文脈での TODO(human) (人間への判定丸投げ) を遮断。
    if _TODO_HUMAN_RE.search(content):
        return True, (
            "[guard-mfk-no-reinvent] 請求確認シート×MF照合の判定を `TODO(human)` で人間に"
            "書かせないでください。判定は実装済みです (lib/mfk_reconcile.py の classify/reconcile)。"
            "`/run-mf-invoice-reconcile --target YYMM` を dry-run→二段確認→`--apply --verified` "
            "の順で使ってください。"
        )

    # R2: 正本以外のファイルへの照合/判定エンジンの再実装を遮断。
    basename = os.path.basename(path.replace("\\", "/"))
    if tool == "Bash":
        targets = _bash_write_targets(content)
        sanctioned = bool(targets) and all(
            os.path.basename(t.replace("\\", "/")) in SANCTIONED_BASENAMES for t in targets
        )
    else:
        sanctioned = basename in SANCTIONED_BASENAMES
    if not sanctioned and _REINVENT_DEF_RE.search(content):
        return True, (
            "[guard-mfk-no-reinvent] 照合/判定ロジックを自作・再実装しないでください "
            f"(検出: {basename})。正本は scripts/reconcile_invoices.py (orchestrator) と "
            "lib/mfk_reconcile.py (reconcile/classify/detect_orphans)、判定SSOTは "
            "schemas/verdict-mapping.json です。`/run-mf-invoice-reconcile` を使ってください。"
        )

    return False, ""


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool = payload.get("tool_name", "")
    ti = payload.get("tool_input", {}) or {}
    blocked, message = evaluate(tool, ti)
    if blocked:
        sys.stderr.write(message + "\n")
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
