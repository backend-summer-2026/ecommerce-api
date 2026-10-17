# AGENTS.md

## Project Rules for Antigravity (`agy`) and AI Agents

### Git Workflow and Branching Strategy
- **Base Branch**: `dev` is the primary development branch.
- **Direct Commits Prohibited**: Never commit directly to `dev` or `main`.
- **Branch Creation**: Always checkout and pull the latest `dev` branch before starting any new task, then create a new branch:
  - `feat/<name>` for new features
  - `fix/<name>` for bug fixes
  - `refactor/<name>` for code refactoring
  - `docs/<name>`, `chore/<name>`, `test/<name>` for other tasks

For full git workflow rules, see [.agents/rules/git-workflow.md](file:///.agents/rules/git-workflow.md).

---

### Agent Permissions and Authority
The `agy` agent is granted autonomous permissions within the workspace:
- **`.agents` Management**: Read and write access to maintain configurations, rules, skills, and hooks inside `.agents/`.
- **Project Execution**: Authorization to run Django development servers, migrations, and management commands (`python manage.py *`).
- **Automated Testing**: Authorization to execute test suites (`python manage.py test`, `pytest`).
- **Code Inspection & Search**: Full permission to use `grep`, `egrep`, `rg`, and `find` across the codebase.

For fine-grained permission grants, see [.agents/permissions.json](file:///.agents/permissions.json) and [.agents/rules/permissions.md](file:///.agents/rules/permissions.md).
