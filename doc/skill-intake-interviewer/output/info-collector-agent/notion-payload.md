# info-collector-agent ヒアリング結果

> Gate A 承認済み・skill-creator 引き渡し可能 / 2026-04-29

## 真の目的

複数情報源を**自分の関心テーマで縦切りキュレーション**し、毎朝**「本日の思考メモ」を Obsidian** に出現させる。それをタネに**今日の企画・戦略を書き始める思考のスタートポイント**にする。

### JTBD
- **When**: 毎朝、企画・戦略を考える時間の前
- **Want to**: 複数ソースを自分の関心テーマで縦切りした思考メモを Obsidian で受け取る
- **So I can**: 情報漁りを省略し、思考と企画に時間とエネルギーを再配分できる

### 表層 → 深層
- **表層**: 情報収集が毎日しんどい・代行してほしい
- **深層**: 単なる収集自動化ではなく、収集→要約→アウトプット化までの一気通貫を代行しないと時間は浮かない
- **差別化**: ニュース要約ではなく「複数ソースを自分の関心テーマで縦方向に下ろす」キュレーション

## 5軸サマリ

| 軸 | 内容 |
|---|---|
| 出力先 | Obsidian Vault（思考メモ本体・最高優先） + Discord/Slack（サマリ通知） |
| 情報源 | 既存3スキル（arxiv-paper-reporter / x-post-reporter / ai-release-reporter）+ 会話URL貼り付け |
| 共有相手 | 自分（最優先）／X／クライアント／チーム（4方向マルチ） |
| 真の課題 | 収集→要約→アウトプット化を一気通貫で代行し、思考に時間を再配分 |
| ナレッジ資産 | Obsidian + 過去X投稿 + 講座資料を参照、暗黙知抽出ハイブリッド、週次更新 |

## 設計選択

- **責務境界**: O1 オーケストレータ（既存3スキルを呼んで成果物を統合）
- **テーマ抽出**: T3 ハイブリッド（手動シード + 動的抽出 + 週次チューニング）
- **配信タイミング**: S3 両対応（cron 定刻 + オンデマンド）

### アウトプット優先順位
1. Obsidian「本日の思考メモ」（最高優先・必須）
2. Discord/Slack 通知（サマリ＋ピン留めシグナル）
3. 副次：X長文・スライド・提案資料への派生は別スキルへ委譲

## ナレッジ抽出パイプライン

- **ingest**: Markdown / X投稿 / URL / PDF
- **analysis**: LLM要約 + Embeddings によるテーマクラスタリング + 静的シードとの統合
- **storage**: Obsidian（人間用）+ JSON テーマ集合ファイル（スキル内部）
- **retrieval**: テーマキーワード検索 + RAG
- **update**: weekly

## 図解（Mermaid ソース）

### 図1. 全体アーキテクチャ
> 既存3スキルの出力をテーマ縦切りで思考メモに変える

\`\`\`mermaid
flowchart LR
    A[X投稿] --> H[テーマ縦切り]
    B[arXiv] --> H
    C[公式発表] --> H
    D[会話URL] --> H
    H --> I[思考メモ生成]
    I --> J[Obsidian]
    I --> K[Discord通知]
\`\`\`

### 図2. テーマ抽出ハイブリッド構造（T3）
> 手動シードを動的補強し週次チューニングで暗黙知追随

\`\`\`mermaid
flowchart TB
    S[手動シード] --> M[統合]
    O[Obsidian過去ノート] --> E[動的抽出]
    X[過去X投稿] --> E
    E --> M
    M --> T[テーマ集合]
    T --> W[週次再学習]
    W -.補強.-> M
\`\`\`

### 図3. 日次パイプライン
> 定刻またはオンデマンドで起動し、テーマ単位の縦切り思考メモを朝に届ける

\`\`\`mermaid
sequenceDiagram
    participant C as cron/手動
    participant O as オーケストレータ
    participant R as 既存3スキル
    participant T as テーマフィルタ
    participant G as 思考メモ生成
    participant U as ユーザー
    C->>O: 起動(定刻 or /info)
    O->>R: 出力ファイル取得
    R-->>O: 収集済みデータ
    O->>T: テーマで縦切り
    T->>G: テーマ別データ
    G-->>U: Obsidian + Discord
\`\`\`

### 図4. Before / After
> 「毎日ゼロから情報を漁る朝」が「思考メモから企画を書き始める朝」に変わる

| Before | After |
|---|---|
| 情報漁り → 整理 → 企画開始遅延 | 朝の思考メモ → 企画着手 → アウトプット |

### 図5. 責務境界
> 既存スキルは「収集の専門家」、このスキルは「思考メモの編集者」として住み分ける

\`\`\`mermaid
flowchart TB
    E1[arxiv-paper-reporter] --> N1[テーマ縦切り]
    E2[x-post-reporter] --> N1
    E3[ai-release-reporter] --> N1
    N1 --> N2[思考メモ生成]
\`\`\`

## 未解決（skill-creator 引き継ぎ事項）

- クライアント実名・契約金額の除外範囲・粒度
- 情報源の絞り込み（X TLアカウント数・arXivカテゴリ範囲）
- Discord/Slack のどちらをメイン通知先にするか
- **テーマ集合ファイルのスキーマと更新ジョブ実装**（ブロッキング）

## skill-creator への申し送り

- `recommended_next.mode = fast-track`
- `skip_to_phase = Phase 2`
- 理由: 5軸全 verified、設計選択も確定済み、要件定義フェーズはスキップ可能
- `intake.json` を起点に Phase 2 から実装着手可能
