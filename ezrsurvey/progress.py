"""Report which item a slow helper is on, with a measured estimate of the time left. Everything goes to stderr, so it never lands in a returned value."""

import math
import time

from .config import ezrsurvey_default
from .rbase import character_value, interactive, message


def progress_on():
    setting = ezrsurvey_default("progress")
    if setting == "auto":
        return interactive()
    return setting is True


def format_duration(seconds):
    if not math.isfinite(seconds):
        return "?"
    if seconds < 90:
        return f"{round(seconds)}s"
    minutes = seconds / 60
    if minutes < 90:
        return f"{round(minutes)}m"
    return f"{character_value(round(minutes / 60, 1))}h"


def progress_plan(title, steps):
    if not progress_on():
        return False
    message(title)
    total = len(steps)
    for i, step in enumerate(steps, start=1):
        message(f"  {i}/{total}  {step}")
    return True


def progress_start(total, label=None):
    """Open a run over `total` items; whether it reports is settled here, once."""
    on = progress_on()
    if on and label is not None:
        message(label)
    return {"total": total, "started": time.monotonic(), "on": on}


def progress_eta(run, i):
    done = i - 1
    if done < 1 or run["total"] <= i:
        return ""
    elapsed = time.monotonic() - run["started"]
    if elapsed < 5:
        return ""
    remaining = (elapsed / done) * (run["total"] - done)
    return f"  (about {format_duration(remaining)} left)"


def progress_item(run, i, name):
    if not run["on"]:
        return False
    message(f"[{i}/{run['total']}] {name}{progress_eta(run, i)}")
    return True


def progress_note(*parts):
    if not progress_on():
        return False
    message(*parts)
    return True


def progress_done(run, note=None):
    if not run["on"]:
        return False
    elapsed = time.monotonic() - run["started"]
    ending = "" if note is None else f", {note}"
    message(f"Done: {run['total']} item(s) in {format_duration(elapsed)}{ending}")
    return True
