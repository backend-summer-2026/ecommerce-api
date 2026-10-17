# Planning and Execution Workflow Rules

## Overview

This document defines the mandatory planning and task execution lifecycle for the `agy` agent in this repository. All non-trivial features, refactoring, architectural modifications, and bug fixes must adhere strictly to this workflow.

---

## 1. Plan Creation & Persistence in `plans/`

- **Mandatory File Persistence**: Whenever a plan is formulated, it must NOT exist solely in conversation messages or temporary scratchpads. It **must be saved as a Markdown (`.md`) file inside the `plans/` directory** at the root of the project.
- **Directory Path**: `plans/` (e.g. `plans/<topic-name>.md` or `plans/<YYYY-MM-DD>-<topic-name>.md`).
- **Standard Plan Structure**:
  Every plan saved in `plans/` must contain:
  1. **Header / Metadata**:
     - **Title**: Clear name of the initiative
     - **Date**: Date created
     - **Status**: `DRAFT` | `APPROVED` | `IN_PROGRESS` | `COMPLETED`
     - **Branch**: Target git branch
  2. **Context & Motivation**: Why this change is necessary and what problem it addresses.
  3. **Architecture & Technical Design**: Detailed technical specifications, models, schemas, endpoints, and libraries.
  4. **Detailed Checklist**: Atomic tasks broken down sequentially.
- **User Presentation**: When introducing a plan, always provide a clickable Markdown file link to the saved plan file (e.g., `[Plan: Auth System](file:///plans/auth-system.md)`).

---

## 2. Plan Approval Requirement

- **No Premature Implementation**: The agent must never start implementing code changes before the user reviews and confirms/approves the plan.
- **Status Transition**: Upon receiving user approval, the agent must update the plan file header status from `DRAFT` to `APPROVED` / `IN_PROGRESS`.
- **Granular Decomposition**: If the plan was initially high-level, upon approval the agent must decompose it into small, atomic, step-by-step checklist tasks.

---

## 3. Checklist-Driven Sequential Execution

- **Atomic Task Sizing**: Every task in the checklist must be small and self-contained (e.g., "Create custom User model", "Write user model tests", "Run makemigrations for users app").
- **Sequential Execution**: Tasks must be tackled strictly one-by-one in sequential order. Do not skip steps or combine multiple distinct checklist items into unverified changes.
- **Checklist Syntax**:
  ```markdown
  ## Execution Checklist

  - [ ] Step 1: Define User and OTP models in `apps/users/models.py`
  - [ ] Step 2: Configure AUTH_USER_MODEL in `config/settings.py`
  - [ ] Step 3: Generate and apply migrations (`makemigrations`, `migrate`)
  - [ ] Step 4: Implement OTP generation and validation utility functions
  - [ ] Step 5: Create serializers and authentication API endpoints
  - [ ] Step 6: Write unit and integration tests for auth workflow
  ```

---

## 4. Real-Time Dynamic Checklist Updates

- **Immediate Marking**: As soon as a checklist task is completed and verified (tests pass, migrations run, code check succeeds), the agent **MUST immediately edit the plan file in `plans/` to mark that specific item as done**:
  ```markdown
  - [x] Step 1: Define User and OTP models in `apps/users/models.py`
  - [ ] Step 2: Configure AUTH_USER_MODEL in `config/settings.py`
  ```
- **Prohibition of Batch Updates**: The agent is strictly prohibited from leaving all items unchecked and then checking them all off together at the end of the session. The file must reflect the true, live progress after each step.
- **Status Communication**: In each response to the user during execution, clearly state:
  1. The task that was just completed and marked `- [x]`.
  2. The next task currently being undertaken (`- [ ]`).

---

## 5. Completion & Final Verification

When all items in the checklist are marked `- [x]`:
1. Execute final verification commands (e.g. `python manage.py check`, test suite).
2. Update the plan status to `COMPLETED` with completion timestamp.
3. Commit the changes and the updated plan file according to [.agents/rules/git-workflow.md](file:///.agents/rules/git-workflow.md).
