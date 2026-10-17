#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

def match_command_rule(cmd: str, rule_target: str) -> bool:
    cmd = cmd.strip()
    rule_target = rule_target.strip()

    if rule_target == "*":
        return True

    if rule_target.startswith("regex:"):
        pattern = rule_target[6:]
        return bool(re.search(pattern, cmd))

    # Prefix match word-by-word
    rule_words = rule_target.split()
    cmd_words = cmd.split()

    if len(cmd_words) < len(rule_words):
        return False

    return cmd_words[:len(rule_words)] == rule_words

def check_permission():
    try:
        raw_input = sys.stdin.read()
        if not raw_input:
            print(json.dumps({"decision": "ask"}))
            return

        payload = json.loads(raw_input)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        args = tool_call.get("args", {})

        base_dir = Path(__file__).resolve().parent.parent
        perms_file = base_dir / "permissions.json"

        if not perms_file.exists():
            print(json.dumps({"decision": "ask"}))
            return

        with open(perms_file, "r") as f:
            perms_data = json.load(f)

        perms = perms_data.get("permissions", {})
        allow_rules = perms.get("allow", [])
        deny_rules = perms.get("deny", [])

        # Parse rules into (action, target)
        parsed_allow = []
        for r in allow_rules:
            m = re.match(r"^([a-z_]+)\((.*)\)$", r.strip())
            if m:
                parsed_allow.append((m.group(1), m.group(2)))

        parsed_deny = []
        for r in deny_rules:
            m = re.match(r"^([a-z_]+)\((.*)\)$", r.strip())
            if m:
                parsed_deny.append((m.group(1), m.group(2)))

        # 1. COMMANDS
        if tool_name == "run_command":
            cmd = args.get("CommandLine", "").strip()

            # Check Deny first
            for action, target in parsed_deny:
                if action in ("command", "unsandboxed"):
                    if match_command_rule(cmd, target):
                        print(json.dumps({
                            "decision": "deny",
                            "reason": f"Command '{cmd}' is blocked by .agents/permissions.json deny rule: {action}({target})"
                        }))
                        return

            # Check Allow
            for action, target in parsed_allow:
                if action in ("command", "unsandboxed"):
                    if match_command_rule(cmd, target):
                        print(json.dumps({"decision": "allow"}))
                        return

        # 2. FILE WRITING / EDITING
        elif tool_name in ("write_to_file", "replace_file_content", "edit_file"):
            target_file = args.get("TargetFile", "")

            # Check Deny
            for action, target in parsed_deny:
                if action == "write_file":
                    if target == "*" or target.rstrip("/") in target_file:
                        print(json.dumps({
                            "decision": "deny",
                            "reason": f"File modification blocked by .agents/permissions.json deny rule: write_file({target})"
                        }))
                        return

            # Check Allow
            for action, target in parsed_allow:
                if action == "write_file":
                    if target == "*" or target.rstrip("/") in target_file:
                        print(json.dumps({"decision": "allow"}))
                        return

        # 3. FILE READING
        elif tool_name in ("view_file", "read_file"):
            target_file = args.get("AbsolutePath", args.get("TargetFile", ""))

            # Check Deny
            for action, target in parsed_deny:
                if action == "read_file":
                    if target == "*" or target.rstrip("/") in target_file:
                        print(json.dumps({
                            "decision": "deny",
                            "reason": f"File reading blocked by .agents/permissions.json deny rule: read_file({target})"
                        }))
                        return

            # Check Allow
            for action, target in parsed_allow:
                if action == "read_file":
                    if target == "*" or target.rstrip("/") in target_file:
                        print(json.dumps({"decision": "allow"}))
                        return

        # Fallback to standard ask prompt
        print(json.dumps({"decision": "ask"}))

    except Exception as e:
        # On unexpected exception, safely fall back to ask
        print(json.dumps({"decision": "ask"}))

if __name__ == "__main__":
    check_permission()
