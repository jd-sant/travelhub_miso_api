from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "pr-test-validation.yml"
SERVICES_DIR = REPO_ROOT / "services"


def _discover_services() -> list[str]:
    services: list[str] = []
    for item in sorted(SERVICES_DIR.iterdir()):
        if not item.is_dir():
            continue
        if (item / "requirements.txt").exists() and (item / "tests").is_dir():
            services.append(item.name)
    return services


def _has_job(text: str, service: str) -> bool:
    return re.search(rf"^\s*test-{re.escape(service)}:\s*$", text, re.MULTILINE) is not None


def _has_needs_entry(text: str, service: str) -> bool:
    return re.search(rf"^\s*-\s*test-{re.escape(service)}\s*$", text, re.MULTILINE) is not None


def main() -> int:
    if not WORKFLOW_PATH.exists():
        print(f"ERROR: Workflow file not found: {WORKFLOW_PATH}")
        return 1

    services = _discover_services()
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

    print("Discovered services:", ", ".join(services))

    missing: list[str] = []

    for service in services:
        output_token = f"{service}: ${{{{ steps.filter.outputs.{service} }}}}"
        filter_token = f"- 'services/{service}/**'"
        result_token = f"needs.test-{service}.result"

        if output_token not in workflow_text:
            missing.append(f"missing detect-changes output for service '{service}'")

        if filter_token not in workflow_text:
            missing.append(f"missing paths-filter rule for service '{service}'")

        if not _has_job(workflow_text, service):
            missing.append(f"missing job 'test-{service}'")

        if not _has_needs_entry(workflow_text, service):
            missing.append(f"missing aggregator needs entry '- test-{service}'")

        if result_token not in workflow_text:
            missing.append(
                f"missing aggregate status validation reference '{result_token}'"
            )

    if missing:
        print("\nCI mapping validation failed:")
        for issue in missing:
            print(f"- {issue}")
        return 1

    print("CI mapping validation passed: all services are wired in PR test workflow.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
