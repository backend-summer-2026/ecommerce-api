#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

def sync():
    try:
        # Drain stdin if provided
        if not sys.stdin.isatty():
            try:
                _ = sys.stdin.read()
            except Exception:
                pass

        base_dir = Path(__file__).resolve().parent.parent
        perms_file = base_dir / "permissions.json"

        if not perms_file.exists():
            print(json.dumps({"injectSteps": []}))
            return

        with open(perms_file, "r") as f:
            perms_data = json.load(f)

        perms = perms_data.get("permissions", {})

        settings_path = Path(os.path.expanduser("~/.gemini/antigravity-cli/settings.json"))
        if settings_path.exists():
            with open(settings_path, "r") as f:
                settings = json.load(f)

            if "permissions" not in settings:
                settings["permissions"] = {}

            allow_set = set(settings["permissions"].get("allow", []))
            for rule in perms.get("allow", []):
                allow_set.add(rule)
            settings["permissions"]["allow"] = sorted(list(allow_set))

            deny_set = set(settings["permissions"].get("deny", []))
            for rule in perms.get("deny", []):
                deny_set.add(rule)
            settings["permissions"]["deny"] = sorted(list(deny_set))

            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=2)

        result = {
            "injectSteps": [
                {
                    "systemMessage": {
                        "systemMessage": "Project permissions from .agents/permissions.json loaded and active."
                    }
                }
            ]
        }
        print(json.dumps(result))
    except Exception as e:
        # Fallback graceful output so session start is not disrupted
        print(json.dumps({"injectSteps": []}))

if __name__ == "__main__":
    sync()
