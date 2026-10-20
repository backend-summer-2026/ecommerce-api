# Git Workflow and Branching Strategy

## Core Principles

- **Primary Development Branch**: `dev` is the base branch for all development work. The `main` branch is strictly reserved for production releases.
- **No Direct Commits to `dev` or `main`**: Never make direct edits or commits directly on `dev` or `main` unless the user explicitly requests otherwise.
- **Branch-Per-Task**: Always branch off from the latest `dev` before starting any coding, fixing, or refactoring task.

---

## Pre-Task Workflow (Mandatory for Every Task)

Before performing any changes (creating files, editing code, running migrations, etc.):

1. **Check Git Status**:
   ```bash
   git status
   ```

2. **Switch to and Update `dev`**:
   ```bash
   git checkout dev
   git pull origin dev
   ```

3. **Create a Dedicated Branch**:
   Choose the appropriate prefix based on the type of work:

   | Task Type | Branch Format | Example |
   | :--- | :--- | :--- |
   | **New Feature** | `feat/<feature-name>` | `feat/product-catalog`, `feat/cart-checkout` |
   | **Bug Fix** | `fix/<bug-name>` | `fix/cart-item-quantity`, `fix/auth-token-expiry` |
   | **Refactoring** | `refactor/<target-name>` | `refactor/order-serializers`, `refactor/user-models` |
   | **Tests** | `test/<test-name>` | `test/products-api`, `test/cart-service` |
   | **Documentation** | `docs/<doc-name>` | `docs/api-endpoints`, `docs/setup-guide` |
   | **Chores / Config** | `chore/<chore-name>` | `chore/update-dependencies`, `chore/docker-setup` |

   Command:
   ```bash
   git checkout -b <branch-name>
   ```

---

## Coding and Verification

1. Make all required changes exclusively inside the new task branch.
2. Verify project integrity before finalizing (e.g., `python manage.py check`, run relevant tests).

---

## Commit Guidelines

Follow the Conventional Commits specification:
- `feat: <description>` for new features
- `fix: <description>` for bug fixes
- `refactor: <description>` for code restructuring
- `chore: <description>` for maintenance and configuration
- `test: <description>` for adding or updating tests
- `docs: <description>` for documentation changes

Example:
```bash
git add .
git commit -m "feat: implement product list and detail views"
```
