# Report 品質チェックリスト（report-quality-reviewer 検証基準 SSOT）

> **正本**: このファイルは report-quality-reviewer から抽出した手続き知識/規範の SSOT。run-slide-report-generate の SKILL.md と agent 本体（agents/report-quality-reviewer.md）の双方がこれを参照する。規則の上位素材は `$CLAUDE_PLUGIN_ROOT/references/report-types.md` / `report-writing-rules.md` / `report-visual-strategy.md`、構成契約は `schemas/report-structure.schema.json` を辿る。

**責務**: report モードの品質検証ドメイン定義（用語集・評価基準・制約カタログ RQCONST_001-007）と検証基準（read-through 多面検証 MUST/SHOULD/MAY チェックリスト・必須検証基準 RQ1〜RQ20・補正指針・よくある問題と対処法）の逐語正本。report-quality-reviewer（薄化アダプタ）は役割・起動条件・I/O契約に専念し、詳細規範は本 reference を SSOT とする。本チェックリストは slide 側 `ui-quality-checklist.md`（S1〜S26 の視覚品質）＋ `layout-optimization-rules.md`（レイアウト補正）に**対応する report 版**であり、slide が「投影 HTML の視覚崩れ」を扱うのに対し report は「読み物としての成立性」を扱う。機械検出可能な項目は決定論ゲート `$CLAUDE_PLUGIN_ROOT/scripts/validate-report-visual.py` に先行させ、意味検証と分離する（RQCONST_001）。

## 用語集
| 用語 | 定義 | 関連概念 |
|------|------|----------|
| 必須検証基準 RQ1〜RQ20 | report.html を read-through 成立性の観点で確認する 20 項目の客観チェック。6 群（読み物文体・段落密度 / 1項目1ビジュアル・図解適合 / reportType 骨格・section 構造 / 見出し階層 / 印刷・letterbox / 可読性・意匠維持） | RQCONST_001-007 |
| 決定論ゲート | `validate-report-visual.py <report.html>`。機械検出可能な崩れ（1項目1ビジュアル超過 / 見出し階層スキップ / 最小フォント違反 / letterbox 強制 / 印刷 px 依存 / 構造同期ずれ）を LLM 検証に先行して確定するスクリプト | RQCONST_001 |
| read-through 粒度 | 投影ではなく通読を前提とした本文密度。文章多め・複数段落を許容 | `$CLAUDE_PLUGIN_ROOT/references/report-writing-rules.md` |
| reportType 骨格 | 目的別に定義された節（role）の必須並び。4 型（internal-analysis/client-proposal/tech-doc/learning） | `$CLAUDE_PLUGIN_ROOT/references/report-types.md` |
| 1項目1ビジュアル | 1 section の非 none visual は最大 1。図解過多を避け読解を助ける 1 点に絞る | `$CLAUDE_PLUGIN_ROOT/references/report-visual-strategy.md` |
| 補正指針 | 検出した崩れに対し「問題・箇所・補正指針」を対応づけた是正案。本エージェントは read_only で指針を返し、実補正は report-composer / slide-report-modifier が行う | I/O 契約 |
| 構造同期 | report.html の内容が report-structure.json の忠実な射影であること（過不足ゼロ） | RQCONST_007 |
| 退化耐性 | コード・数値・料金・精密表など逐語が変わる要素を画像に焼かず本文（表/コード）で持つこと | slide CONST_007 相当 |

## 評価基準（ドメイン固有の判定基準）
| 基準 | 条件 |
|------|------|
| RQ1〜RQ20 合否 | 全 20 項目が客観条件を満たす=合格 / 違反=補正指針を確定（上流起因は差し戻し） |
| 機械/LLM 分離 | 機械検出可能な項目は決定論ゲートで先行確定 / 意味検証（読み物成立・段落密度品質・種別適合・骨格論理順序）は LLM が担う（RQCONST_001） |
| 段落密度 | brief=各節1-2 段落 / standard=2-4 段落 / deep=3 段落以上。1段落1論点・トピックセンテンス先行（過密/過疎は補正） |
| 1項目1ビジュアル | 各 section の非 none visual が最大 1（超過は補正 or 節分割） |
| 最小フォントサイズ | 本文最小 1.4rem 以上（read-through でも割らない） |
| コントラスト比 | WCAG 2.1 AA（4.5:1）以上で合格 / 未満は不合格 |
| 骨格順守 | 確定 reportType の必須 role が sections[] に順序通り網羅（欠落は差し戻し・省略は理由明示） |
| 補正指針ループ収束 | 補正指針の反映→再検証が 3 周以内で全基準充足=収束 / 3周で未収束=エスカレーション |

## ビジネスルール（制約カタログ RQCONST_001-007）

- **RQCONST_001 (機械検証先行ゲート)**: 決定論ゲート `validate-report-visual.py <report.html>` を LLM 意味検証に**先行**して実行し、機械検出可能な崩れ（1項目1ビジュアル超過 / 見出し階層スキップ / 最小フォント違反 / letterbox 強制 / 印刷 px 依存 / 構造同期ずれ）を確定してから意味検証に入る。
  - 目的: 機械で確定できる崩れを LLM の主観・記憶に委ねず、機械検証と意味検証を分離する。
  - 背景: The Checklist Manifesto の知見。機械層で捕れる項目を先に潰すことで、LLM は読み物成立・段落密度品質・種別適合・骨格論理順序という意味判断に集中できる。
- **RQCONST_002 (read-through 成立)**: 各 section は見出しだけで終わらせず、要点を言い切る段落を持つ。空節・箇条書きだけの節は退化。chip 強制・長文禁止を緩和した read-through 粒度を守る。
  - 目的: 「見出しと chip の羅列」ではなく「読める文書」にする。
  - 背景: report は slide の長文禁止（BP11-13）・chip 強制を緩和する。文章多めが正（`$CLAUDE_PLUGIN_ROOT/references/report-writing-rules.md`）。
- **RQCONST_003 (段落密度)**: length（brief/standard/deep）に応じた段落密度を守り、1段落1論点・トピックセンテンス先行にする。過密（1 段落に論点が混在）・過疎（節が痩せる）を補正する。
  - 目的: 通読の負荷を length 相応に保ち、論点を追える文書にする。
  - 背景: report-writing-rules §2.1 段落・§2.3 length 方針。
- **RQCONST_004 (1項目1ビジュアル・図解過多回避)**: 1 section の非 none visual は最大 1。全節に図解を付ける図解過多を避け、要る節に 1 点、文章で足りる節は none にする。
  - 目的: 読解を助ける 1 点に絞り、装飾過多で本文が痩せるのを防ぐ。
  - 背景: report-visual-strategy §2。複数図が欲しくなったら情報過密のサインとして節分割を検討する。
- **RQCONST_005 (reportType 骨格順守)**: 確定 reportType の必須 role を sections[] に網羅し、論理順序（背景→結論 / 前提→手順 / 問い→まとめ）を崩さない。骨格節を省く場合は省略理由を明示する（無言の省略はしない）。
  - 目的: 読者が文脈（背景・前提）を得た上で結論・手順へ到達できるようにする。
  - 背景: report-types §5「順序保持は絶対」。骨格欠落は上流起因として report-structure-designer へ差し戻す。
- **RQCONST_006 (意匠維持ライン)**: 本文最小 1.4rem・Kanagawa 配色（純黒/純白回避）・印刷 CSS・退化耐性（逐語を画像に焼かない）を維持する。配色・フォント・印刷 CSS は共有 SSOT から適用し report 独自に発明しない。
  - 目的: slide/report の意匠を単一 SSOT に保ち、可読性下限と退化耐性を両モードで共通化する。
  - 背景: report-writing-rules §3 維持ライン。緩和するのはコンテンツ意図層のみ、意匠/技術層は共有（build-contract §D）。
- **RQCONST_007 (構造同期)**: report.html は report-structure.json の忠実な射影で過不足ゼロにする。勝手に節を増減しない。
  - 目的: 承認済み構造からの逸脱を防ぐ。
  - 背景: 構造化データ先行。生成は構造の忠実な射影であり、同期崩れは report-composer へ差し戻す。

## read-through 多面検証チェックリスト（MUST / SHOULD / MAY）

出力の「品質基準（出力に必ず含む必須フィールド）」を満たすため、以下の多面検証チェックリストを全件消化する。

必須（MUST）読み物成立・骨格:

- [ ] 各 section に空でない段落があり、見出しだけの空節が 0 件（RQCONST_002）
- [ ] length（brief/standard/deep）相応の段落密度で、1段落1論点・トピックセンテンス先行（RQCONST_003）
- [ ] 各 section の非 none visual が最大 1 で、図解過多になっていない（RQCONST_004）
- [ ] 確定 reportType の必須 role が sections[] に順序通り網羅されている（RQCONST_005）
- [ ] 骨格節を省く場合は省略理由が本文冒頭の断り等で明示されている（RQCONST_005）
- [ ] report.html が report-structure.json の忠実な射影で過不足ゼロ（RQCONST_007）

必須（MUST）意匠・可読性:

- [ ] 本文最小 1.4rem 以上（read-through でも割らない・RQCONST_006）
- [ ] WCAG AA（コントラスト比 4.5:1 以上）を満たす
- [ ] Kanagawa 配色で純黒（#000000）・純白（#FFFFFF）を本文に使っていない
- [ ] 配色・フォント・印刷 CSS を共有 SSOT から適用し report 独自発明がない（RQCONST_006）
- [ ] コード・数値・料金・精密表を画像に焼かず本文（markdown 表/コードブロック）で持つ（退化耐性）

必須（MUST）構造・レイアウト:

- [ ] h1（タイトル）→ h2（section 見出し）→ h3（下位）の見出し階層がスキップなしで整合
- [ ] 各読み単位が「見出し＋段落＋最大1ビジュアル＋callouts」の構造を保つ
- [ ] A4/レター読み物レイアウト（縦スクロール）で report を 16:9 letterbox に強制していない
- [ ] 印刷 CSS が共有 SSOT トークン（mm/rem・px 依存なし）で適用され印刷時に本文・図が欠落しない

推奨（SHOULD）:

- [ ] 各 visual.kind が内容適合（一次判定/tie-break で説明可能・rationale 記載）
- [ ] readingOrder が 1 方向に統一・focalPoint が同じ高さ帯に揃っている（配置一貫性）
- [ ] 注意点/警告が callouts（note/warning/tip/caution）で目立たせられている
- [ ] 強調（`**…**`）が要点に限られ乱用されていない
- [ ] 見出しが内容を表す自然な長さで、折り返し前提で成立している

任意（MAY）:

- [ ] 参照リンク（外部仕様・出典）が付されている
- [ ] 目次・アンカーで長文の可読性が補助されている
- [ ] 印刷用の改ページ位置が節境界に整っている

## 検証基準（必須検証基準 RQ1〜RQ20）

各基準は第三者が合否判定できる客観条件で記述し、agent の完了チェックリスト（5.3）はこれらを全件消化することで充足する。決定論ゲートで機械検出可能な項目（検出方法欄に「機械」を付記）は LLM 意味検証に先行して確定する（RQCONST_001）。

### A 群: 読み物文体・段落密度（RQ1〜RQ4）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ1 | 空節ゼロ | 各 section.paragraphs[] が空でなく要点を言い切る。見出しだけの空節が 0 件 | report.html の各 section 内 `<p>` 有無を確認（機械＋意味） |
| RQ2 | 段落密度上限 | length に応じた段落数（brief=各節1-2 / standard=2-4 / deep=3+）を大きく超過/下回らない | 各 section の段落数を length と照合（意味） |
| RQ3 | 1段落1論点 | 各段落の先頭にトピックセンテンス、論点混在なし | 段落先頭文と後続文の論点一致を確認（意味） |
| RQ4 | 長文自然性 | slide の 20 字 `<br>` 強制を適用せず段落として自然に書けている（chip 強制で痩せていない） | 段落中の不自然な `<br>` 連発の不在を確認（機械＋意味） |

### B 群: 1項目1ビジュアル・図解適合（RQ5〜RQ8）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ5 | 1項目1ビジュアル | 各 section の非 none visual（svg/mermaid/codex-image）が最大 1 | section 内のビジュアル要素数をカウント（機械） |
| RQ6 | 図解過多回避 | 全 section に図解を付けていない。文章で足りる節は none | none section の存在と図解偏在を確認（意味） |
| RQ7 | 種別適合 | visual.kind が内容適合（構造=svg/mermaid・情感=codex-image・論述=none の一次判定に整合）で rationale がある | report-structure.json の visual.kind と rationale を照合（意味） |
| RQ8 | 退化耐性 | コード・数値・料金・精密表を画像に焼いていない（本文の表/コードで持つ） | 画像 alt/caption と本文表・コードブロックの所在を確認（機械＋意味） |

### C 群: reportType 骨格・section 構造（RQ9〜RQ12）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ9 | 骨格網羅 | 確定 reportType の必須 role が sections[] に 1 つ以上ずつ写像されている | reportType の必須 role 集合と sections[].role を照合（機械） |
| RQ10 | 骨格順序保持 | role の論理順序（背景→結論 / 前提→手順 / 問い→まとめ）を崩していない | sections[].role の並びを骨格順と照合（意味） |
| RQ11 | 省略明示 | 骨格節を省く場合、省略理由が本文冒頭の断り等で明示されている（無言の省略なし） | 欠落 role に対する断り書きの有無を確認（意味） |
| RQ12 | section 構造 | 各読み単位が「見出し＋段落＋最大1ビジュアル＋callouts」の構造を保ち、注意点/警告が callouts で表現 | section の構成要素と callouts 使用を確認（機械＋意味） |

### D 群: 見出し階層（RQ13〜RQ14）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ13 | 見出し階層整合 | h1（タイトル）→ h2（section 見出し）→ h3（下位）がスキップなしで整合（h2 の直下で h4 に飛ばない） | `grep "<h[1-6]"` で見出しレベルの並びを確認（機械） |
| RQ14 | 見出し自然長 | 見出しが内容を表す自然な長さ（slide の最大文字数・改行位置ルールは非適用） | 見出しテキスト長と内容表現性を確認（意味） |

### E 群: 印刷・letterbox（RQ15〜RQ16）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ15 | read-through レイアウト | A4/レター読み物レイアウト（縦スクロール）で report を 16:9 letterbox に強制していない（letterbox は slide 固有） | `aspect-ratio: 16/9` 等の letterbox 強制の不在を確認（機械） |
| RQ16 | 印刷品質 | 印刷 CSS が共有 SSOT トークン（mm/rem・px 依存なし）で適用され、印刷時に本文・図が欠落しない | `@media print` の単位（px 依存の不在）とレイアウトを確認（機械） |

### F 群: 可読性・意匠維持（RQ17〜RQ20）

| # | 検証項目 | 基準（検証可能条件） | 検出方法 |
|---|---------|------|----------|
| RQ17 | 最小フォント | 本文相当テキストが 1.4rem 以上（read-through でも割らない） | `grep "font-size:[0-9.]*rem"` で 1.4rem 未満を検出（機械） |
| RQ18 | コントラスト | WCAG AA（4.5:1）以上、Kanagawa 配色で純黒/純白を本文に使わない | 前景背景の色差を確認、`#000000`/`#FFFFFF` の本文使用を検出（機械＋意味） |
| RQ19 | 意匠共有 | 配色・フォント・印刷 CSS を共有 SSOT から適用し report 独自発明がない | 意匠トークンが共有 SSOT 由来か確認（意味） |
| RQ20 | 構造同期 | report.html が report-structure.json の忠実な射影で過不足ゼロ（勝手な節の増減なし） | sections 数と各 section 内容を report.html と照合（機械） |

**RQ9・RQ20 に違反（骨格欠落・構造同期崩れ）がある場合、上流起因として report-structure-designer / report-composer へ差し戻す。その他の RQ 違反は補正指針を返し report-composer / slide-report-modifier が適用する。**

## 補正指針（検出問題→補正指針）

検出問題ごとの補正指針。本エージェントは read_only で指針を返し、実補正は下流（report-composer / slide-report-modifier）が適用する。font-size 縮小は最小値（1.4rem）以上の範囲でのみ行う。

| 問題 | 補正指針 |
|------|----------|
| 空節（見出しだけ） | 結論文＋根拠段落を加筆する（report-composer へ） |
| 段落過密（1段落に論点混在） | 論点で段落を分割し、各段落先頭にトピックセンテンスを置く |
| 段落過疎（節が痩せる） | 背景・根拠・含意を加筆、または length を見直す |
| 1項目1ビジュアル超過 | 図解を 1 点に絞る。2 点必要なら情報過密のサインとして節分割を report-structure-designer へ |
| 図解過多（全節に図） | 文章で足りる節を none 化する |
| 種別不適合 | 内容の性質（構造/情感/論述/逐語）に合わせ kind を再選択し rationale を更新 |
| 逐語を画像に焼いている | 数値・料金・コードを本文（markdown 表/コードブロック）へ移す（退化耐性） |
| 骨格 role 欠落 | 必須 role を補うか省略理由を明示（差し戻し: report-structure-designer） |
| 骨格順序崩れ | role の並びを骨格の論理順序へ是正（差し戻し: report-structure-designer） |
| 見出し階層スキップ | 中間見出しを補うか下位見出しレベルを是正 |
| letterbox 強制 | 16:9 の aspect-ratio を外し A4/レター縦スクロールへ戻す |
| 印刷 px 依存 | 印刷 CSS の px を mm/rem へ、共有 SSOT トークンへ整合 |
| 最小フォント違反 | CSS 変数（--fs-body 等）で 1.4rem 以上へ |
| コントラスト不足 | テーマの色変数を使い WCAG AA を満たす。純黒/純白を避ける |
| 意匠独自発明 | 共有 SSOT（vendor primitives / theme）の意匠トークンへ差し替え |
| 構造同期崩れ | report-structure.json を正として過不足を是正（差し戻し: report-composer） |

## よくある問題と対処法

### 読み物文体・段落密度

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 見出しと chip だけで本文がない | slide 規律を report にそのまま適用 | 各節に結論文＋根拠段落を書く（read-through 緩和） |
| slide をそのまま縦に並べた | 1メッセージ圧縮が通読を阻害 | セクション＋段落へ再構成する |
| 段落が長すぎ論点混在 | 1段落に複数論点 | 論点で分割しトピックセンテンス先行に |
| deep 指定なのに各節1段落 | 密度が length と不整合 | 背景・根拠・含意まで加筆 |

### 1項目1ビジュアル・図解適合

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 1節に図解2点 | 情報過密 | 1点に絞る or 節分割（report-structure-designer へ） |
| 全節に図解 | 図解過多 | 文章で足りる節は none |
| 数値・料金を画像に焼いた | 退化耐性違反 | markdown 表で本文に持つ |
| codex-image を構造図に使用 | 種別不適合 | 構造は svg/mermaid へ寄せる |

### reportType 骨格・section 構造

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 必須 role 欠落 | 骨格未網羅 | role を補う or 省略理由明示（差し戻し） |
| 背景の前に結論だけ | 論理順序崩れ | 骨格順へ並べ替え（差し戻し） |
| callouts を使わず警告が埋没 | 注記手段の未使用 | 落とし穴・補足を callouts（warning/caution）で強調 |

### 見出し階層・印刷/letterbox

| 問題 | 原因 | 対処法 |
|------|------|--------|
| h2 の直下で h4 | 見出しレベルスキップ | h3 を経る or 中間見出しを補う |
| report が 16:9 に固定 | slide の letterbox を誤適用 | aspect-ratio を外し縦スクロールへ |
| 印刷でカードが消える | 印刷 CSS の px 依存/box-shadow 依存 | mm/rem・border で輪郭を明示、共有トークンへ |

### 可読性・意匠維持

| 問題 | 原因 | 対処法 |
|------|------|--------|
| 本文が 1.4rem 未満 | 直書き小サイズ | CSS 変数で 1.4rem 以上へ |
| 純白テキストが眩しい | #FFFFFF 使用 | --fg（Kanagawa 淡色）へ |
| 独自配色を発明 | 意匠 SSOT 非共有 | 共有トークンへ差し替え（RQCONST_006） |
| report.html が構造と不一致 | 勝手な節の増減 | report-structure.json を正に是正（差し戻し） |
