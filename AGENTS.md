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

---

### Planning and Execution Workflow
Every new feature, refactoring, or architectural change must follow a strict planning lifecycle:
- **Plan Persistence in `plans/`**: Every plan created must be saved as a Markdown file in `plans/<topic-name>.md`. Plans must not exist only in transient chat messages.
- **Plan Approval**: Do not start code implementation until the plan is reviewed and approved by the user.
- **Checklist Breakdown**: Upon approval, decompose the plan into small, atomic, sequential checklist items (`- [ ] Step ...`).
- **Real-Time Checklist Updates**: Execute tasks sequentially and update the checklist in the plan file immediately as each task is completed (`- [ ]` -> `- [x]`). Do not batch checklist updates at the end.

For the complete planning rules, see [.agents/rules/planning-workflow.md](file:///.agents/rules/planning-workflow.md).

---

### API & Postman Collection Maintenance
The master Postman collection serves as the central specification for testing business logic end-to-end:
- **Mandatory Synchronization**: Whenever an API endpoint is created, updated (URL, parameters, headers, body), or removed, the master Postman collection in `postman/ecommerce_api_collection.json` must be updated immediately.
- **Business Logic Testing**: Every request in the collection must include realistic request payloads, authentication headers, and automatic token-chaining scripts where applicable.
- **Checklist Requirement**: Every API plan's checklist must include a task to update the Postman collection before task completion.

For full Postman maintenance rules, see [.agents/rules/postman-workflow.md](file:///.agents/rules/postman-workflow.md).

