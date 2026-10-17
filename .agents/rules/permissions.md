# Agent Permissions and Execution Rules

## Overview

This document specifies the permissions and operational authority granted to the `agy` agent when working on the `ecommerce` project. The agent has autonomous access to execute tasks, search code, run test suites, and manage `.agents/` configuration.

---

## 1. `.agents` Folder Permissions

The agent has full read and write permissions inside the `.agents/` directory and related project configuration:
- **Rules Management**: Create, edit, and update rule files in `.agents/rules/`.
- **Permissions Management**: Maintain `.agents/permissions.json` and rule references.
- **Skills & Hooks**: Create and configure custom skills (`.agents/skills/`) and lifecycle hooks (`.agents/hooks.json`).
- **Root References**: Maintain `AGENTS.md` and related root-level configuration files.

---

## 2. Project Execution Permissions

The agent is authorized to run project commands without requiring manual confirmation:
- **Server Execution**:
  ```bash
  python manage.py runserver
  ```
- **Integrity & Configuration Checks**:
  ```bash
  python manage.py check
  ```
- **Database Migrations**:
  ```bash
  python manage.py makemigrations
  python manage.py migrate
  python manage.py showmigrations
  ```
- **Django Shell & Utilities**:
  ```bash
  python manage.py shell
  python manage.py collectstatic --noinput
  ```

---

## 3. Testing Permissions

The agent is fully authorized to run all automated test suites to validate code quality and bug fixes:
- **Django Test Runner**:
  ```bash
  python manage.py test
  python manage.py test <app_name>
  python manage.py test <app_name>.tests.<TestClass>
  ```
- **Pytest**:
  ```bash
  pytest
  pytest <path/to/test_file.py>
  ```
- **Python Unittest**:
  ```bash
  python -m unittest discover
  ```

---

## 4. Search and Code Inspection Permissions

The agent is authorized to use search and inspection utilities across the workspace:
- **Grep & RegEx Search**:
  ```bash
  grep -rn "<pattern>" .
  egrep -rn "<pattern>" .
  ```
- **Ripgrep & File Finding**:
  ```bash
  rg "<pattern>"
  find . -name "<pattern>"
  ```

---

## 5. Precedence and Safety Boundaries

- **Allowed Scope**: Operations strictly within this project workspace (`ecommerce`).
- **Safety Boundary**: Destructive global file deletions (e.g., `rm -rf /` or operations outside the workspace root) are strictly prohibited.
- **Git Compliance**: All changes must adhere to [.agents/rules/git-workflow.md](file:///.agents/rules/git-workflow.md) (branching off `dev`, no direct commits to `dev` or `main`).
