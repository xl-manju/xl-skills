# prompt-creator (DEPRECATED)

> ⚠️ **このディレクトリは 2026-05-21 に deprecated となりました。**

## 移行先

正本は `plugins/prompt-creator/` に移動しました:

- Skill: `plugins/prompt-creator/skills/run-prompt-creator-7layer/`
- SubAgent: `plugins/prompt-creator/agents/prompt-creator-{interview-user,generate-prompt,review-prompt}.md`
- manifest: `plugins/prompt-creator/.claude-plugin/plugin.json`

## 移行内容

skill-creator 仕様準拠で以下を適用:

- SKILL.md / SubAgent 各 300 行以下
- 責務分離: Prompt Templates / Self-Evaluation 注入のみを担当
- Progressive Disclosure: references/ は Phase 直前読み込み
- Node 標準のみ (package.json / npm 依存撤去)
- skill-creator (run-build-skill Step 7.5) からループ呼び出し対応

## 保持理由

Git 履歴・移行証跡確保のため doc 側は残置。新規参照・編集はすべて `plugins/prompt-creator/` 側を使用してください。
