#!/usr/bin/env python3
"""
run_all.py — Prescia Maps master pipeline runner with resume support.

Runs the full data pipeline in sequence:
  1. scripts/USminesscraper.py           — US mines (USGS MRDS)
  2. scripts/Ghosttownsscraper.py        — Ghost towns & abandoned places
  3. scripts/Historicscraper.py          — Historic places, battles, forts (+ Wikidata)
  4. scripts/load_battles_seed.py        — 371 pre-verified US battle locations
  5. scripts/load_stagecoach_geojson.py  — Stagecoach route LineString features
  6. scripts/stitch_routes.py            — Route stitching (skipped if missing)
  7. scripts/enrich_locations.py         — Enrichment pass (Wikipedia, reclassify)

Resume support:
  A checkpoint file (pipeline_checkpoint.json) tracks the status of each step.
  On restart without --fresh, completed steps are skipped automatically.

Usage::

    python run_all.py --fresh            # full pipeline from scratch
    python run_all.py                    # resume from last checkpoint
    python run_all.py --only enrich      # run only enrichment
    python run_all.py --skip stitch      # skip route-stitching
    python run_all.py --dry-run --state CO --limit 1000
    python run_all.py --verbose          # full sub-script output
"""

from __future__ import annotations

import io
import sys

# Force UTF-8 output on Windows to prevent emoji/unicode crashes
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import subprocess

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent
CHECKPOINT_FILE = REPO_ROOT / "pipeline_checkpoint.json"

SCRIPTS = {
    "mines": REPO_ROOT / "scripts" / "USminesscraper.py",
    "ghosttowns": REPO_ROOT / "scripts" / "Ghosttownsscraper.py",
    "historic": REPO_ROOT / "scripts" / "Historicscraper.py",
    "battles": REPO_ROOT / "scripts" / "load_battles_seed.py",
    "stagecoach": REPO_ROOT / "scripts" / "load_stagecoach_geojson.py",
    "stitch": REPO_ROOT / "scripts" / "stitch_routes.py",
    "enrich": REPO_ROOT / "scripts" / "enrich_locations.py",
}

STEP_ORDER: List[str] = [
    "mines", "ghosttowns", "historic", "battles", "stagecoach", "stitch", "enrich",
]

STEP_LABELS: Dict[str, str] = {
    "mines": "USminesscraper",
    "ghosttowns": "Ghosttownsscraper",
    "historic": "Historicscraper",
    "battles": "load_battles_seed",
    "stagecoach": "load_stagecoach_geojson",
    "stitch": "stitch_routes",
    "enrich": "enrich_locations",
}

# Steps that accept --state
STATE_STEPS = frozenset(["mines", "ghosttowns", "historic"])
# Steps that accept --limit
LIMIT_STEPS = frozenset(["mines", "ghosttowns", "historic", "enrich"])
# Steps that accept --fresh
FRESH_STEPS = frozenset(["mines", "ghosttowns", "historic", "battles", "stitch", "enrich"])
# Steps that accept --dry-run
DRY_RUN_STEPS = frozenset([
    "mines", "ghosttowns", "historic", "battles", "stagecoach", "stitch", "enrich",
])

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

ANSI_SUPPORTED = sys.stdout.isatty()

_ESC = "\033"
_CLEAR_LINE = f"{_ESC}[2K"

_HIDE_CURSOR = f"{_ESC}[?25l"
_SHOW_CURSOR = f"{_ESC}[?25h"
_RESET = f"{_ESC}[0m"
_BOLD = f"{_ESC}[1m"
_GREEN = f"{_ESC}[32m"
_YELLOW = f"{_ESC}[33m"
_RED = f"{_ESC}[31m"
_CYAN = f"{_ESC}[36m"
_DIM = f"{_ESC}[2m"


def _ansi(code: str) -> str:
    return code if ANSI_SUPPORTED else ""


def _fmt_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def _step_icon(status: str) -> str:
    return {
        "completed": "✅",
        "in_progress": "🔄",
        "failed": "❌",
        "pending": "⏳",
        "skipped": "⏭️ ",
    }.get(status, "⏳")


# ---------------------------------------------------------------------------
# Checkpoint management
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_checkpoint() -> Optional[Dict]:
    if CHECKPOINT_FILE.exists():
        try:
            with CHECKPOINT_FILE.open() as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_checkpoint(data: Dict) -> None:
    try:
        with CHECKPOINT_FILE.open("w") as f:
            json.dump(data, f, indent=2)
    except OSError as exc:
        print(f"Warning: could not save checkpoint: {exc}", file=sys.stderr)


def delete_checkpoint() -> None:
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


def new_checkpoint(fresh: bool = False) -> Dict:
    return {
        "run_id": _now_iso(),
        "fresh": fresh,
        "steps": {
            step: {"status": "pending"}
            for step in STEP_ORDER
        },
    }


# ---------------------------------------------------------------------------
# Progress display
# ---------------------------------------------------------------------------

# Number of lines the display occupies (header + step lines + footer)
_DISPLAY_LINES = 3 + len(STEP_ORDER) + 2  # banner(3) + steps + blank + elapsed


class ProgressDisplay:
    """In-place terminal progress display using ANSI escape codes."""

    def __init__(self, checkpoint: Dict, verbose: bool = False) -> None:
        self.checkpoint = checkpoint
        self.verbose = verbose
        self._step_status: Dict[str, str] = {}        # step → last status line
        self._step_start: Dict[str, float] = {}       # step → monotonic start time
        self._pipeline_start = time.monotonic()
        self._first_render = True
        self._lines_written = 0

        for step in STEP_ORDER:
            self._step_status[step] = ""

    def update_status(self, step: str, line: str) -> None:
        self._step_status[step] = line
        if not self.verbose:
            self._render()

    def log_line(self, step: str, line: str) -> None:
        """Log a raw output line (used in verbose mode or non-ANSI fallback)."""
        if self.verbose or not ANSI_SUPPORTED:
            label = STEP_LABELS.get(step, step)
            print(f"  [{label}] {line}")

    def step_started(self, step: str) -> None:
        self._step_start[step] = time.monotonic()
        self.checkpoint["steps"][step] = {
            "status": "in_progress",
            "started_at": _now_iso(),
        }
        save_checkpoint(self.checkpoint)
        if not self.verbose:
            self._render()

    def step_done(self, step: str, success: bool) -> None:
        elapsed = 0.0
        if step in self._step_start:
            elapsed = time.monotonic() - self._step_start[step]
        status = "completed" if success else "failed"
        self.checkpoint["steps"][step].update(
            {
                "status": status,
                "completed_at": _now_iso(),
                "duration_s": round(elapsed, 1),
            }
        )
        save_checkpoint(self.checkpoint)
        if not self.verbose:
            self._render()

    def step_skipped(self, step: str) -> None:
        self.checkpoint["steps"][step]["status"] = "skipped"
        save_checkpoint(self.checkpoint)
        if not self.verbose:
            self._render()

    def _render(self) -> None:
        if not ANSI_SUPPORTED:
            return

        lines: List[str] = []

        # Banner
        lines.append(f"{_ansi(_BOLD)}{'═' * 67}{_ansi(_RESET)}")
        lines.append(f"{_ansi(_BOLD)}  Prescia Maps — Full Data Pipeline{_ansi(_RESET)}")
        lines.append(f"{_ansi(_BOLD)}{'═' * 67}{_ansi(_RESET)}")
        lines.append("")

        total = len(STEP_ORDER)
        for idx, step in enumerate(STEP_ORDER, 1):
            sdata = self.checkpoint["steps"].get(step, {})
            status = sdata.get("status", "pending")
            icon = _step_icon(status)
            label = STEP_LABELS[step]
            extra = ""

            if status == "completed":
                dur = sdata.get("duration_s", 0)
                extra = f"{_ansi(_GREEN)}— Done  ({_fmt_duration(dur)}){_ansi(_RESET)}"
            elif status == "in_progress":
                msg = self._step_status.get(step, "Running…")
                extra = f"{_ansi(_CYAN)}— {msg}{_ansi(_RESET)}"
            elif status == "failed":
                extra = f"{_ansi(_RED)}— FAILED{_ansi(_RESET)}"
            elif status == "skipped":
                extra = f"{_ansi(_DIM)}— Skipped{_ansi(_RESET)}"
            else:
                extra = f"{_ansi(_DIM)}— Pending{_ansi(_RESET)}"

            lines.append(f"[{idx}/{total}] {icon} {label:<22} {extra}")

        lines.append("")
        elapsed = time.monotonic() - self._pipeline_start
        lines.append(
            f"{_ansi(_DIM)}Elapsed: {_fmt_duration(elapsed)}{_ansi(_RESET)}"
        )

        output = "\n".join(lines)

        if not self._first_render and self._lines_written > 0:
            # Move cursor up to overwrite previous render
            sys.stdout.write(f"\r{_ESC}[{self._lines_written}A")
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
        self._lines_written = len(lines)
        self._first_render = False

    def print_summary(self) -> bool:
        """Print final summary table. Returns True if all steps succeeded/skipped."""
        if not self.verbose and ANSI_SUPPORTED:
            # Re-render once more to show final state
            self._render()

        print()
        print(f"{_ansi(_BOLD)}{'─' * 67}{_ansi(_RESET)}")
        print(f"{_ansi(_BOLD)}  Pipeline Summary{_ansi(_RESET)}")
        print(f"{_ansi(_BOLD)}{'─' * 67}{_ansi(_RESET)}")

        all_ok = True
        for step in STEP_ORDER:
            sdata = self.checkpoint["steps"].get(step, {})
            status = sdata.get("status", "pending")
            icon = _step_icon(status)
            label = STEP_LABELS[step]
            dur = sdata.get("duration_s")
            dur_str = f"  ({_fmt_duration(dur)})" if dur else ""
            if status not in ("completed", "skipped"):
                all_ok = False
            color = (
                _GREEN if status == "completed"
                else _RED if status == "failed"
                else _DIM
            )
            print(f"  {icon} {label:<22} {_ansi(color)}{status}{_ansi(_RESET)}{dur_str}")

        print(f"{_ansi(_BOLD)}{'─' * 67}{_ansi(_RESET)}")
        total_elapsed = time.monotonic() - self._pipeline_start
        print(f"  Total time: {_fmt_duration(total_elapsed)}")
        print()
        return all_ok


# ---------------------------------------------------------------------------
# Log-line parsing
# ---------------------------------------------------------------------------

# Patterns to extract a meaningful status line from sub-script output
_PROGRESS_PATTERNS = [
    re.compile(r"Progress:(.+)", re.IGNORECASE),
    re.compile(r"(\d[\d,]* (?:processed|inserted|records?|rows?).*)", re.IGNORECASE),
    re.compile(r"(Done\..*)", re.IGNORECASE),
    re.compile(r"(Completed.*)", re.IGNORECASE),
    re.compile(r"(Inserted \d.*)", re.IGNORECASE),
    re.compile(r"(Fetching.*)", re.IGNORECASE),
    re.compile(r"(Downloading.*)", re.IGNORECASE),
    re.compile(r"(Processing.*)", re.IGNORECASE),
    re.compile(r"(Enriching.*)", re.IGNORECASE),
    re.compile(r"(Stitching.*)", re.IGNORECASE),
    re.compile(r"(\[.*\].*%.*)", re.IGNORECASE),  # tqdm-like bars
]


def _extract_status(line: str) -> Optional[str]:
    """Return a condensed status string from a log line, or None."""
    clean = line.strip()
    if not clean:
        return None
    for pat in _PROGRESS_PATTERNS:
        m = pat.search(clean)
        if m:
            return m.group(1).strip()[:120]
    return None


# ---------------------------------------------------------------------------
# Step runner
# ---------------------------------------------------------------------------

def _build_args(step: str, args: argparse.Namespace) -> List[str]:
    """Build CLI arguments to pass to a sub-script."""
    extra: List[str] = []
    if args.fresh and step in FRESH_STEPS:
        extra.append("--fresh")
    if args.dry_run and step in DRY_RUN_STEPS:
        extra.append("--dry-run")
    if args.state and step in STATE_STEPS:
        extra += ["--state", args.state]
    if args.limit and step in LIMIT_STEPS:
        extra += ["--limit", str(args.limit)]
    return extra


def run_step(
    step: str,
    script: Path,
    extra_args: List[str],
    display: ProgressDisplay,
    verbose: bool,
) -> bool:
    """
    Run a single pipeline step.
    Returns True on success, False on failure.
    """
    display.step_started(step)

    cmd = [sys.executable, str(script)] + extra_args
    env = os.environ.copy()

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )
    except OSError as exc:
        display.update_status(step, f"Failed to start: {exc}")
        display.step_done(step, success=False)
        return False

    try:
        for raw_line in proc.stdout:  # type: ignore[union-attr]
            line = raw_line.rstrip("\n")
            display.log_line(step, line)
            status = _extract_status(line)
            if status and not verbose:
                display.update_status(step, status)

        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise

    success = proc.returncode == 0
    display.step_done(step, success=success)
    if not success:
        print(
            f"\n{_ansi(_RED)}✗ Step '{step}' failed with exit code {proc.returncode}.{_ansi(_RESET)}",
            file=sys.stderr,
        )
    return success


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prescia Maps — master pipeline runner with resume support.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        default=False,
        help="Delete pipeline checkpoint and pass --fresh to all sub-scripts.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Pass --dry-run to all sub-scripts (no DB writes).",
    )
    parser.add_argument(
        "--state",
        metavar="XX",
        default=None,
        help="Filter by US state abbreviation (passed to scraper scripts).",
    )
    parser.add_argument(
        "--skip",
        metavar="STEP",
        action="append",
        default=[],
        dest="skip",
        help=(
            "Skip a named step. Can be repeated. "
            "Step names: mines, ghosttowns, historic, battles, stagecoach, stitch, enrich."
        ),
    )
    parser.add_argument(
        "--only",
        metavar="STEP",
        action="append",
        default=[],
        dest="only",
        help="Run ONLY the named step(s). Can be repeated.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Pass --limit N to scraper scripts.",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        default=False,
        help=(
            "Ignore existing checkpoint and re-run all steps "
            "(but don't pass --fresh to sub-scripts, so their internal "
            "checkpoints are preserved)."
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show full sub-script output instead of parsed summary lines.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # Validate step names in --skip / --only
    all_valid = set(STEP_ORDER)
    for step in args.skip + args.only:
        if step not in all_valid:
            print(
                f"Error: unknown step '{step}'. Valid steps: {', '.join(STEP_ORDER)}",
                file=sys.stderr,
            )
            return 1

    # Determine which steps to run
    if args.only:
        steps_to_run = [s for s in STEP_ORDER if s in args.only]
    else:
        steps_to_run = [s for s in STEP_ORDER if s not in args.skip]

    # Handle checkpoint
    if args.fresh:
        delete_checkpoint()
        checkpoint = new_checkpoint(fresh=True)
        save_checkpoint(checkpoint)
    elif args.no_resume:
        checkpoint = new_checkpoint(fresh=False)
        save_checkpoint(checkpoint)
    else:
        checkpoint = load_checkpoint() or new_checkpoint(fresh=False)
        save_checkpoint(checkpoint)

    display = ProgressDisplay(checkpoint, verbose=args.verbose)

    if not args.verbose and ANSI_SUPPORTED:
        sys.stdout.write(_HIDE_CURSOR)
        sys.stdout.flush()

    overall_success = True

    try:
        for step in steps_to_run:
            script = SCRIPTS[step]
            sdata = checkpoint["steps"].get(step, {})
            current_status = sdata.get("status", "pending")

            # Skip completed steps (unless --no-resume or --fresh)
            if current_status == "completed" and not args.fresh and not args.no_resume:
                if ANSI_SUPPORTED and not args.verbose:
                    display._render()
                else:
                    print(f"  ⏭  [{step}] Already completed — skipping.")
                continue

            # Check if script exists
            if not script.exists():
                if step == "stitch":
                    print(
                        f"\n{_ansi(_YELLOW)}⚠ stitch_routes.py not found — skipping "
                        f"gracefully.{_ansi(_RESET)}",
                        flush=True,
                    )
                    display.step_skipped(step)
                    continue
                else:
                    print(
                        f"\n{_ansi(_RED)}✗ Script not found: {script}{_ansi(_RESET)}",
                        file=sys.stderr,
                    )
                    display.step_done(step, success=False)
                    overall_success = False
                    continue

            extra_args = _build_args(step, args)
            success = run_step(step, script, extra_args, display, verbose=args.verbose)
            if not success:
                overall_success = False
            # Continue to next step regardless of failure

    except KeyboardInterrupt:
        print(
            f"\n\n{_ansi(_YELLOW)}⚠ Interrupted by user. "
            f"Checkpoint saved to {CHECKPOINT_FILE.name}.{_ansi(_RESET)}",
            flush=True,
        )
        save_checkpoint(checkpoint)
        return 130
    finally:
        if not args.verbose and ANSI_SUPPORTED:
            sys.stdout.write(_SHOW_CURSOR)
            sys.stdout.flush()

    # Print summary
    display.print_summary()

    # Clean up checkpoint on full success
    if overall_success:
        delete_checkpoint()

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
