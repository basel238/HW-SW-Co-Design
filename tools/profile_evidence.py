"""Strict py-spy capture checks and separately labelled measured-stack selection."""
import re


def assess_python_capture(returncode, stdout, stderr, raw, receipt_errors, driver_path):
    result = {"usable": False, "capture_status": "failed", "returncode": returncode,
              "sample_count": 0, "measured_sample_count": 0, "excluded_sample_count": 0,
              "warning": None, "errors": list(receipt_errors),
              "roi_selection": "Stacks containing run_measured_calls in the exact driver path; not perf gating."}
    rows, measured = [], []
    marker = re.compile(r"^run_measured_calls \(" + re.escape(str(driver_path)) + r":\d+\)$")
    for number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            stack, token = line.rsplit(" ", 1)
            if not re.fullmatch(r"[1-9][0-9]*", token) or not all(f.strip() for f in stack.split(";")):
                raise ValueError
            count = int(token)
        except ValueError:
            result["errors"].append("Malformed folded row " + str(number))
            continue
        rows.append((line, count))
        if any(marker.fullmatch(frame) for frame in stack.split(";")):
            measured.append((line, count))
    total = sum(count for _, count in rows)
    result.update(sample_count=total, measured_sample_count=sum(count for _, count in measured))
    result["excluded_sample_count"] = total - result["measured_sample_count"]
    if not total:
        result["errors"].append("No positive samples")
    if not measured:
        result["errors"].append("No measured-call marker observed; cannot generate an ROI graph")
    reports = re.findall(r"Samples:\s*(\d+)\s+Errors:\s*(\d+)", stdout)
    if len(reports) != 1 or int(reports[0][0]) != total or int(reports[0][1]) != 0:
        result["errors"].append("Sampler sample/error totals do not validate the raw capture")
    known_exit_warning = (returncode == 1 and stderr.strip() == "Error: No child process (os error 10)"
                          and "Stopped sampling because process exited" in stdout
                          and "Wrote raw flamegraph data" in stdout)
    if returncode and not known_exit_warning:
        result["errors"].append("Sampler failed with an unrecognized error")
    if not result["errors"]:
        result["usable"] = True
        result["capture_status"] = "complete_with_sampler_exit_warning" if known_exit_warning else "complete"
        if known_exit_warning:
            result["warning"] = "Known child-reaping error after a validated complete capture; original exit retained."
    return result, "\n".join(line for line, _ in measured) + ("\n" if measured else "")
