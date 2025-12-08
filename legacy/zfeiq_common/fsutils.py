import os
import re

def find_main_dir(start_path: str = None) -> str:
    """Search upward from start_path (or this file) for a directory containing `main.py`.
    Returns the directory path if found, otherwise falls back to two levels up from
    this module's location.
    """
    if start_path is None:
        curr = os.path.abspath(os.path.dirname(__file__))
    else:
        curr = os.path.abspath(start_path)

    while True:
        if os.path.exists(os.path.join(curr, "main.py")):
            return curr
        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent

    # fallback: two levels above this module (best-effort)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def ensure_dir(path: str) -> str:
    """Ensure directory exists under project common directory.

    Behavior:
    - All directories (relative or absolute) are created under
      <project_main_dir>/common/<relpath-or-basename>.
      This avoids creating nested absolute-path-like folders when code
      runs on a different OS or with a different CWD.
    - Returns the absolute path created.
    - Raises on invalid input or underlying os.makedirs errors.
    """
    if not path:
        raise ValueError("empty path")

    # compute a relative component to place under common
    # Treat Windows-style absolute paths (e.g. 'E:\\... or E:/...') as external
    # and reduce them to their basename when running on non-Windows hosts.
    is_windows_abs = bool(re.match(r"^[A-Za-z]:[\\/].*", path))
    if os.path.isabs(path) or is_windows_abs:
        rel = os.path.basename(path.rstrip(os.sep))
    else:
        # keep subpaths if provided (e.g. 'screenshots/sub')
        rel = path.lstrip(os.sep)

    if not rel:
        raise ValueError(f"invalid path component derived from: {path}")

    base = find_main_dir()
    final = os.path.join(base, "common", rel)

    # create directories with sane default permissions
    try:
        os.makedirs(final, exist_ok=True, mode=0o755)
    except TypeError:
        os.makedirs(final, exist_ok=True)

    # best-effort: ensure writable
    try:
        if not os.access(final, os.W_OK):
            os.chmod(final, 0o755)
    except Exception:
        pass

    return os.path.abspath(final)
