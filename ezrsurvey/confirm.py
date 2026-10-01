"""Show an automatically chosen selection and wait for a yes before a long run. Scripts never wait, because the prompt only appears in an interactive session."""

from .config import ezrsurvey_default
from .rbase import interactive, message, strwrap


def confirm_on(setting=None):
    if setting is None:
        setting = ezrsurvey_default("confirm")
    if setting == "auto":
        return interactive()
    if not isinstance(setting, bool):
        raise ValueError(f'`confirm` must be True, False, or "auto", not {type(setting).__name__}.')
    return setting


def confirm_lines(label, names):
    if not names:
        return [f"{label}: none"]
    text = f"{label} ({len(names)}): " + ", ".join(names)
    return strwrap(text, width=76, exdent=4)


def read_answer(prompt):
    """What the user typed, or "" outside an interactive session, as R's readline() gives."""
    if not interactive():
        return ""
    return input(prompt)


def confirm_selection(title, lines, setting=None):
    """Print what the call is about to do and ask whether to go ahead; Enter means yes."""
    if not confirm_on(setting):
        return True
    message(title)
    for line in lines:
        message("  ", line)
    answer = read_answer("Continue? [Y/n] ").strip().lower()
    return answer not in ("n", "no")
