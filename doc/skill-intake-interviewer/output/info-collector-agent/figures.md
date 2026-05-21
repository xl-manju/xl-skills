# 図解集（info-collector-agent）

各図に「言いたい一言」を1行付記。ノード数 7±2、日本語10文字以内、Font Awesome アイコン使用。

---

## 図1. 全体アーキテクチャ（オーケストレータ構造）

**言いたい一言**: 既存3スキルの出力を「関心テーマ」で縦切りにして思考メモに変える。

```mermaid
flowchart LR
    A[fa:fa-twitter X投稿] --> H[fa:fa-layer-group<br/>テーマ縦切り]
    B[fa:fa-file-lines arXiv] --> H
    C[fa:fa-bullhorn 公式発表] --> H
    D[fa:fa-comments 会話URL] --> H
    H --> I[fa:fa-brain 思考メモ生成]
    I --> J[fa:fa-book Obsidian]
    I --> K[fa:fa-bell Discord通知]

    classDef src fill:#e8f4fd,stroke:#3182ce
    classDef core fill:#fef3c7,stroke:#d97706
    classDef out fill:#d1fae5,stroke:#059669
    class A,B,C,D src
    class H,I core
    class J,K out
```

**凡例**: 青=情報源 / 黄=このスキルのコア / 緑=出力先

---

## 図2. テーマ抽出ハイブリッド構造（T3）

**言いたい一言**: 手動シードを動的補強し、週次でチューニングして暗黙知を追随する。

```mermaid
flowchart TB
    S[fa:fa-seedling 手動シード<br/>テーマ初期集合] --> M[fa:fa-merge 統合]
    O[fa:fa-folder-open Obsidian過去ノート] --> E[fa:fa-magnifying-glass<br/>動的抽出]
    X[fa:fa-clock-rotate-left 過去X投稿] --> E
    E --> M
    M --> T[fa:fa-tags テーマ集合]
    T --> W[fa:fa-arrows-rotate 週次再学習]
    W -.補強.-> M

    classDef static fill:#e8f4fd,stroke:#3182ce
    classDef dyn fill:#fef3c7,stroke:#d97706
    classDef out fill:#d1fae5,stroke:#059669
    class S static
    class O,X,E dyn
    class M,T,W out
```

**凡例**: 青=静的入力 / 黄=動的抽出 / 緑=統合とフィードバック

---

## 図3. 日次パイプライン（毎朝の流れ）

**言いたい一言**: 定刻またはオンデマンドで起動し、テーマ単位の縦切り思考メモを朝に届ける。

```mermaid
sequenceDiagram
    participant C as fa:fa-clock cron/手動
    participant O as fa:fa-robot オーケストレータ
    participant R as fa:fa-database 既存3スキル
    participant T as fa:fa-tags テーマフィルタ
    participant G as fa:fa-pen 思考メモ生成
    participant U as fa:fa-user ユーザー

    C->>O: 起動(定刻 or /info)
    O->>R: 出力ファイル取得
    R-->>O: 収集済みデータ
    O->>T: テーマで縦切り
    T->>G: テーマ別データ
    G-->>U: Obsidian + Discord
```

**凡例**: 起動経路は2系統（cron / オンデマンド）、最終出力は2方向（Obsidian / Discord）

---

## 図4. Before / After（毎朝の風景）

**言いたい一言**: 「毎日ゼロから情報を漁る朝」が「思考メモから企画を書き始める朝」に変わる。

```mermaid
flowchart LR
    subgraph Before [Before / 現状]
        B1[fa:fa-magnifying-glass 情報漁り] --> B2[fa:fa-spinner 整理] --> B3[fa:fa-circle-exclamation 企画開始遅延]
    end
    subgraph After [After / 完成後]
        A1[fa:fa-mug-hot 朝の思考メモ] --> A2[fa:fa-lightbulb 企画着手] --> A3[fa:fa-rocket アウトプット]
    end

    classDef bad fill:#fee2e2,stroke:#dc2626
    classDef good fill:#d1fae5,stroke:#059669
    class B1,B2,B3 bad
    class A1,A2,A3 good
```

**凡例**: 赤=現状の摩擦 / 緑=完成後の理想

---

## 図5. 責務境界（既存スキル群との関係）

**言いたい一言**: 既存スキルは「収集の専門家」、このスキルは「思考メモの編集者」として住み分ける。

```mermaid
flowchart TB
    subgraph 既存 [既存スキル / 収集レイヤー]
        E1[fa:fa-file-lines arxiv-paper-reporter]
        E2[fa:fa-twitter x-post-reporter]
        E3[fa:fa-bullhorn ai-release-reporter]
    end
    subgraph 新規 [info-collector-agent / 思考メモ編集レイヤー]
        N1[fa:fa-layer-group テーマ縦切り]
        N2[fa:fa-pen 思考メモ生成]
    end
    E1 --> N1
    E2 --> N1
    E3 --> N1
    N1 --> N2

    classDef exist fill:#e8f4fd,stroke:#3182ce
    classDef new fill:#fef3c7,stroke:#d97706
    class E1,E2,E3 exist
    class N1,N2 new
```

**凡例**: 青=既存資産（再利用） / 黄=新規責務（このスキルが担う領域）

---

## visualization-mandatory-rules チェック

- [x] ノード数 7±2 を全図遵守
- [x] 日本語ラベル10文字以内
- [x] 色凡例つき（青/黄/緑/赤の意味付き）
- [x] Font Awesome アイコン使用（絵文字なし）
- [x] 各図に「言いたい一言」付記
- [x] 専門用語は最小化（「縦切り」「思考メモ」など平易語）
