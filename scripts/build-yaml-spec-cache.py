#!/usr/bin/env python3
"""build-yaml-spec-cache.py

Claude Code 公式の YAML frontmatter / settings 仕様を取得し、
`.claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md`
に書き出す。GitHub Actions の `update-yaml-spec.yml` から週次起動される。

CONVENTIONS:
- stdlib only (urllib, html.parser, datetime, pathlib, sys)
- 禁止依存: requests, PyYAML, bs4
- shebang + main + sys.exit(main()) パターン
"""
import datetime
import html.parser
import pathlib
import sys
import urllib.error
import urllib.request

SOURCES = [
    ("skills", "https://docs.claude.com/en/docs/claude-code/skills"),
    ("settings", "https://docs.claude.com/en/docs/claude-code/settings"),
    ("subagents", "https://docs.claude.com/en/docs/claude-code/sub-agents"),
]

OUT_PATH = pathlib.Path(
    ".claude/skills/ref-yaml-spec-fetcher/references/yaml-spec-cache.md"
)
MAX_BODY_CHARS = 50000
FETCH_TIMEOUT_SEC = 30


class TextExtractor(html.parser.HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self.skip_depth > 0:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "xl-skills-yaml-spec-fetcher/1.0"}
    )
    with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_body(html_doc: str) -> str:
    parser = TextExtractor()
    parser.feed(html_doc)
    return parser.text()[:MAX_BODY_CHARS]


def main() -> int:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    lines = [
        "# YAML Spec Cache",
        "",
        f"last_fetched: {now}",
        "fetcher: scripts/build-yaml-spec-cache.py",
        "",
    ]
    failures = 0
    for name, url in SOURCES:
        lines.append(f"## Source ({name}): {url}")
        lines.append("")
        try:
            body = extract_body(fetch(url))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            body = f"FETCH_FAILED: {type(exc).__name__}: {exc}"
            failures += 1
        lines.append(body)
        lines.append("")
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT_PATH} (sources={len(SOURCES)}, failures={failures})")
    return 0 if failures == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
