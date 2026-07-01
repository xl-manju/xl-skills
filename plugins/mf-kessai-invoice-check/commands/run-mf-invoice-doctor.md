---
name: run-mf-invoice-doctor
description: MF掛け払い請求書チェックのセットアップ状態(APIキー/API疎通/Notionトークン/DB到達)を1コマンドで自己診断したいとき、疎通確認をしたいときに使う。
argument-hint: "[--json]"
allowed-tools: Read, Bash
---

# /run-mf-invoice-doctor

MF掛け払い請求書チェックのセットアップを横断自己診断する。(1) MF掛け払い APIキーの Keychain 取得可否、(2) MF API 疎通 (GET `/customers`・読み取りのみ)、(3) Notion トークン取得可否、(4) 既定 Notion DB への到達を、それぞれ **OK / WARN / SKIP** で一覧表示する。**鍵・トークン本体は表示しません**(マスクのみ)。
Marketplace から install した場合の呼び出し名は通常 `/mf-kessai-invoice-check:run-mf-invoice-doctor`。

> **疎通確認はこのコマンド(または「MF掛け払いのセットアップを確認して」と自然文で依頼)で行ってください。** 生ターミナルで `python3 "$CLAUDE_PLUGIN_ROOT/lib/..."` を手打ちすると、`$CLAUDE_PLUGIN_ROOT` が未定義で空展開し `can't open file '/lib/...'` になります(→ README「トラブルシュート」)。このコマンドは**セットアップ確認専用**で、MF/Notion とも**読み取りのみ**・請求データやトークンには一切書き込みません。

## 振る舞い

1. 下記スクリプトを実行し、各チェックの OK / WARN / SKIP を一覧表示する。
2. WARN があっても処理は止めない (WARN-not-FAIL の診断ツール)。表示された「次アクション」を実施して再実行する。
3. install 位置は `__file__` 相対で自己解決するため、リポジトリ / マーケットプレースのどちらでも動く (`$CLAUDE_PLUGIN_ROOT` 未定義でも lib は自己解決)。

## 実行コード

```bash
python3 "${CLAUDE_PLUGIN_ROOT:-plugins/mf-kessai-invoice-check}/lib/mfk_doctor.py"
```
