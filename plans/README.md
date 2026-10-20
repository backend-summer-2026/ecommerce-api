# Plans Directory

This directory stores all project execution plans, architectural designs, and implementation checklists created by the `agy` agent and developers.

## Conventions

- Every new feature, major refactor, or architectural change must have an associated plan file saved here before implementation begins (e.g., `plans/<topic-name>.md` or `plans/<YYYY-MM-DD>-<topic-name>.md`).
- Each plan must contain:
  1. Header with Metadata (Title, Date, Status, Branch)
  2. Context & Objectives
  3. Technical / Architectural Design
  4. Execution Checklist (`- [ ] Task ...`)
- Once approved, the agent breaks the plan down into atomic tasks and marks them `- [x]` in real-time as each item is completed.

For detailed rules and guidelines, see [.agents/rules/planning-workflow.md](file:///.agents/rules/planning-workflow.md).
