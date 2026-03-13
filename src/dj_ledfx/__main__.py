from __future__ import annotations

import os
import sys


def _should_reexec_under_pyspy() -> bool:
    """Check if we should re-exec under py-spy for sampling profiling."""
    if os.environ.get("_LEDFX_UNDER_PYSPY"):
        return False
    if "--profile" not in sys.argv:
        return False
    # Don't re-exec for --profile deep (VizTracer handles it in main.py)
    try:
        idx = sys.argv.index("--profile")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "deep":
            return False
    except ValueError:
        return False
    return True


def _reexec_under_pyspy() -> None:
    """Re-exec the current process under py-spy record."""
    import shutil
    import subprocess
    from datetime import datetime
    from pathlib import Path

    pyspy = shutil.which("py-spy")
    if pyspy is None:
        print(
            "ERROR: py-spy not found. Install with: uv pip install py-spy",
            file=sys.stderr,
        )
        sys.exit(1)

    profiles_dir = Path("profiles")
    profiles_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = profiles_dir / f"profile-{timestamp}.json"

    # Strip --profile [sampling] from args for the child process
    remaining_args: list[str] = []
    skip_next = False
    for i, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if arg == "--profile":
            # Check if next arg is "sampling" (skip it too)
            next_idx = i + 2  # +1 for sys.argv[1:] offset, +1 for next
            if next_idx < len(sys.argv) and sys.argv[next_idx] == "sampling":
                skip_next = True
            continue
        remaining_args.append(arg)

    env = os.environ.copy()
    env["_LEDFX_UNDER_PYSPY"] = "1"

    # Use sys.executable to re-invoke under the same Python interpreter
    cmd = [
        pyspy,
        "record",
        "--format",
        "speedscope",
        "-o",
        str(output_path),
        "--",
        sys.executable,
        "-m",
        "dj_ledfx",
        *remaining_args,
    ]

    print(f"Starting py-spy profiler, output: {output_path}")
    try:
        result = subprocess.run(cmd, env=env)
        print(f"\nProfile saved to: {output_path}")
        print("Open at: https://www.speedscope.app/ (load local file)")
        sys.exit(result.returncode)
    except PermissionError:
        print(
            "ERROR: py-spy needs elevated permissions on macOS.\n"
            "Try: sudo uv run -m dj_ledfx --profile\n"
            "Or disable SIP: https://github.com/benfred/py-spy#how-do-i-run-py-spy-in-docker--macOS",
            file=sys.stderr,
        )
        sys.exit(1)


if _should_reexec_under_pyspy():
    _reexec_under_pyspy()
else:
    from dj_ledfx.main import main

    main()
