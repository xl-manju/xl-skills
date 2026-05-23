# codex 接続仕様 (スタブ)

## 前提

- `codex` CLI がローカルにインストール済み。`scripts/check-codex-installed.py` で確認する。
- 認証は CLI 側に委ねる。本 Skill は credential を扱わない。

## 呼び出し形式 (暫定)

```bash
codex review --input eval-log/delegate-codex-request.json \
             --output eval-log/delegate-codex-response.json \
             --system-prompt-file references/system-prompt.md
```

TODO(human): 実 CLI の subcommand 体系を確認し確定する。

## I/O 契約

`schemas/io-contract.schema.json` を正本とする。input/output いずれも JSON。

## 失敗時の挙動

- codex 未導入 -> verdict=skipped で正常終了。
- codex タイムアウト -> 1 回までリトライ。それでも失敗なら verdict=skipped, severity=warn。
- 応答が schema 違反 -> verdict=fail (codex 側の責務不全として記録)。
