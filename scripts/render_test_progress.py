from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _collect_pytest_nodes(collect_output: Path) -> list[str]:
    nodes: list[str] = []
    for line in collect_output.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "::" not in line:
            continue
        if line.endswith("tests collected in 0.00s"):
            continue
        if line.startswith("<") or line.startswith("=="):
            continue
        nodes.append(line)
    return nodes


def _parse_pytest_junit(xml_path: Path) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    if not xml_path.exists():
        return result
    tree = ET.parse(xml_path)
    root = tree.getroot()
    for testcase in root.iter("testcase"):
        status = "passed"
        if testcase.find("failure") is not None or testcase.find("error") is not None:
            status = "failed"
        elif testcase.find("skipped") is not None:
            status = "skipped"
        result.append({
            "status": status,
            "time": testcase.attrib.get("time", "0"),
        })
    return result


def _parse_matrix_summary(summary_path: Path) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    if not summary_path.exists():
        return result
    for line in summary_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        result[str(record["step"])] = {
            "status": "passed" if int(record["exit_code"]) == 0 else "failed",
            "exit_code": int(record["exit_code"]),
            "log": str(record["log"]),
        }
    return result


def _format_success_time(value: str | None) -> str:
    return value or "never"


def main() -> int:
    if len(sys.argv) != 7:
        print(
            "Usage: render_test_progress.py COLLECT_OUTPUT PYTEST_XML MATRIX_SUMMARY STATE_JSON OUTPUT_MD RUN_AT",
            file=sys.stderr,
        )
        return 1

    collect_output = Path(sys.argv[1])
    pytest_xml = Path(sys.argv[2])
    matrix_summary = Path(sys.argv[3])
    state_json = Path(sys.argv[4])
    output_md = Path(sys.argv[5])
    run_at = sys.argv[6]

    previous_state = _load_json(state_json, {"pytest": {}, "matrix": {}})
    state = {
        "snapshot": {
            "last_verified_at": run_at,
            "pytest_collect_output": str(collect_output),
            "pytest_xml": str(pytest_xml),
            "matrix_summary": str(matrix_summary),
        },
        "pytest": {},
        "matrix": {},
    }

    collected_nodes = _collect_pytest_nodes(collect_output)
    collected_results = _parse_pytest_junit(pytest_xml)
    matrix_results = _parse_matrix_summary(matrix_summary)

    pytest_prev = previous_state.get("pytest", {})
    matrix_prev = previous_state.get("matrix", {})

    passed_pytest = failed_pytest = skipped_pytest = 0
    for index, nodeid in enumerate(collected_nodes):
        prev = pytest_prev.get(nodeid, {})
        current = collected_results[index] if index < len(collected_results) else {}
        status = current.get("status", "not_run")
        if status == "passed":
            passed_pytest += 1
        elif status == "failed":
            failed_pytest += 1
        elif status == "skipped":
            skipped_pytest += 1
        last_success_at = prev.get("last_success_at")
        if status == "passed":
            last_success_at = run_at
        state["pytest"][nodeid] = {
            "status": status,
            "last_exit_code": 0 if status == "passed" else 1 if status == "failed" else None,
            "last_run_at": run_at,
            "last_success_at": last_success_at,
        }

    passed_matrix = failed_matrix = 0
    for step, info in matrix_results.items():
        prev = matrix_prev.get(step, {})
        status = str(info.get("status", "not_run"))
        if status == "passed":
            passed_matrix += 1
        elif status == "failed":
            failed_matrix += 1
        last_success_at = prev.get("last_success_at")
        if status == "passed":
            last_success_at = run_at
        state["matrix"][step] = {
            "status": status,
            "last_exit_code": info.get("exit_code"),
            "last_run_at": run_at,
            "last_success_at": last_success_at,
            "log": info.get("log"),
        }

    # Preserve rows that existed before but were not in the current summaries.
    for step, prev in matrix_prev.items():
        if step not in state["matrix"]:
            state["matrix"][step] = prev
    for nodeid, prev in pytest_prev.items():
        if nodeid not in state["pytest"]:
            state["pytest"][nodeid] = prev

    _write_json(state_json, state)

    lines: list[str] = []
    lines.append("# Test Progress")
    lines.append("")
    lines.append("This file is generated by `scripts/update_test_progress.sh`.")
    lines.append("")
    lines.append("## Snapshot")
    lines.append("")
    lines.append(f"- Last verified: `{run_at}`")
    lines.append(f"- Pytest collect file: `{collect_output}`")
    lines.append(f"- Pytest junit xml: `{pytest_xml}`")
    lines.append(f"- Matrix summary: `{matrix_summary}`")
    lines.append("")
    lines.append("## Pytest Suite")
    lines.append("")
    lines.append(f"- Passed: {passed_pytest}")
    lines.append(f"- Failed: {failed_pytest}")
    lines.append(f"- Skipped: {skipped_pytest}")
    lines.append("")
    for nodeid in collected_nodes:
        entry = state["pytest"][nodeid]
        status = entry["status"]
        icon = "x" if status == "passed" else " " if status in {"failed", "not_run"} else "-"
        last_success = _format_success_time(entry.get("last_success_at"))
        exit_code = entry.get("last_exit_code")
        extra = f" - exit `{exit_code}`" if exit_code is not None and status != "passed" else ""
        lines.append(
            f"- [{icon}] `{nodeid}` - `{status}`{extra} - last success `{last_success}`"
        )

    lines.append("")
    lines.append("## Grev Matrix")
    lines.append("")
    lines.append(f"- Passed: {passed_matrix}")
    lines.append(f"- Failed: {failed_matrix}")
    lines.append("")
    for step in sorted(state["matrix"]):
        entry = state["matrix"][step]
        status = entry["status"]
        icon = "x" if status == "passed" else " "
        last_success = _format_success_time(entry.get("last_success_at"))
        log = entry.get("log")
        extra = f" - log `{log}`" if log else ""
        lines.append(f"- [{icon}] `{step}` - `{status}`{extra} - last success `{last_success}`")

    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- `passed` means the latest run exited cleanly.")
    lines.append("- `failed` means the latest run failed; the previous success time is preserved if any.")
    lines.append("- `never` means the test has not passed yet.")

    output_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
