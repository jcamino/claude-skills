#!/usr/bin/env python3
"""Dispatch a self-contained brief to agy, grok or codex in its own git worktree.

The calling agent owns the merge. This script never commits and never touches
the caller's working tree: the delegate runs in a worktree created for it, and
the caller reviews `git diff` before deciding anything.

Set DELEGATE_DRYRUN=1 to do every local step (worktree, brief, argv resolution)
and stop before the one step that costs tokens.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

RUNS_DIR = Path.home() / ".claude" / "delegate-runs"

# Which quota each CLI bills against. Reported in the announce line so the
# caller can see what a dispatch costs before it happens.
QUOTA = {
    "agy": "Antigravity / Google",
    "grok": "xAI",
    "codex": "OpenAI",
}

# Permission flags per CLI. These are not equivalent across the three and none
# of them is a security boundary -- the worktree is what actually contains a
# misbehaving delegate.
#
# "read" means the delegate may read and run commands but may not write; it does
# NOT mean a planning mode. codex's and agy's planning modes deny command
# execution outright, and since both reach files through commands, a delegate in
# one of them cannot even read the tree it was pointed at (measured 2026-09-09:
# codex returned "blocked by policy", agy returned an empty response with
# denied_actions=[RunCommand]). approval_policy=never keeps codex from raising an
# approval that non-interactive exec has nobody to answer.
MODE_FLAGS = {
    "agy": {"read": ["--sandbox"], "write": ["--mode", "accept-edits"]},
    "grok": {
        "read": ["--permission-mode", "dontAsk", "--disallowed-tools", "edit,write"],
        "write": ["--permission-mode", "acceptEdits"],
    },
    "codex": {
        "read": ["-s", "read-only", "-c", 'approval_policy="never"'],
        "write": ["-s", "workspace-write", "-c", 'approval_policy="never"'],
    },
}

# --unsandboxed. codex's Windows sandbox rejects CreateProcess for *every* shell
# on this machine -- pwsh (a WindowsApps alias) and powershell.exe 5.1 alike, all
# "blocked by policy" -- and agy denies RunCommand under every non-permissive
# mode. Neither can so much as read a file without these flags, so the practical
# choice here is an unsandboxed delegate inside a throwaway worktree or no
# delegate at all. Containment is then the worktree alone: measured 2026-09-09,
# codex under -C <worktree> wrote only inside it and left the main checkout
# clean. grok needs none of this and is left sandboxed.
#
# The real fix is `codex doctor`'s Defender exclusions; until those are added
# this flag is the workaround, and it is opt-in on purpose.
UNSANDBOXED_FLAGS = {
    "codex": ["--dangerously-bypass-approvals-and-sandbox"],
    "agy": ["--dangerously-skip-permissions"],
    "grok": [],
}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug or "task")[:40]


def git(*args: str, cwd: Path | None = None) -> str:
    out = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def build_argv(cli: str, mode: str, brief: Path, workdir: Path, args) -> list[str]:
    """Resolve the exact argv for one CLI. No shell, ever -- a brief passed as a
    shell string gets its backslashes eaten before any shell sees it."""
    # An unsandboxed run replaces the permission flags rather than joining them:
    # codex rejects --dangerously-bypass-approvals-and-sandbox alongside -s.
    # grok has no entry, so it keeps its normal flags either way -- it is the one
    # CLI whose sandbox works here.
    perm = (UNSANDBOXED_FLAGS[cli] if args.unsandboxed and UNSANDBOXED_FLAGS[cli]
            else MODE_FLAGS[cli][mode])
    exe = resolve_exe(cli)

    if cli == "codex":
        argv = [exe, "exec", *perm, "-C", str(workdir), "--json",
                "-o", str(args._last_message)]
        if args.model:
            argv += ["-m", args.model]
        argv += ["-"]  # brief arrives on stdin
        return argv

    if cli == "grok":
        argv = [exe, "--prompt-file", str(brief), "--cwd", str(workdir),
                "--output-format", "json", *perm]
        if args.model:
            argv += ["-m", args.model]
        if args.max_turns:
            argv += ["--max-turns", str(args.max_turns)]
        return argv

    # agy has neither --prompt-file nor --cwd: the brief goes through argv (safe,
    # because subprocess never invokes a shell). --add-dir is what actually points
    # it at the worktree -- agy does NOT treat the child process's cwd as its
    # workspace, and without this its edits land in
    # ~/.gemini/antigravity-cli/scratch instead (measured 2026-09-09, in a
    # worktree and in a full clone alike). With --add-dir, writes land correctly
    # even when the brief only says "your current working directory".
    argv = [exe, "-p", brief.read_text(encoding="utf-8"),
            "--add-dir", str(workdir),
            "--output-format", "json", *perm]
    if args.model:
        argv += ["--model", args.model]
    if args.timeout:
        argv += ["--print-timeout", f"{args.timeout}s"]
    return argv


def extract_spend(cli: str, stdout: str) -> dict:
    """Pull whatever the CLI volunteers about what the call cost. grok reports
    dollars outright; agy reports tokens; codex reports neither in --json."""
    try:
        if cli == "grok":
            data = json.loads(stdout)
            return {"cost_usd": data.get("total_cost_usd"),
                    "tokens": (data.get("usage") or {}).get("total_tokens"),
                    "turns": data.get("num_turns")}
        if cli == "agy":
            data = json.loads(stdout)
            return {"cost_usd": None,
                    "tokens": (data.get("usage") or {}).get("total_tokens"),
                    "turns": data.get("num_turns"),
                    "denied_actions": data.get("denied_actions") or []}
    except (json.JSONDecodeError, AttributeError):
        pass
    return {}


def resolve_exe(name: str) -> str:
    """Absolute path to the CLI. On Windows an npm-installed CLI is a `.CMD`
    shim, which `subprocess` will not find by bare name the way a shell does --
    `grok` resolves for `command -v` and raises FileNotFoundError here."""
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(name)
    return found


def display(argv: list[str]) -> str:
    """Readable form of the argv. Paths stay intact so a dry-run command can be
    copied and run; only a genuinely huge argument (agy's inlined brief) is cut."""
    parts = []
    for a in argv:
        shown = a if len(a) <= 200 else a[:197].replace("\n", " ") + "..."
        parts.append(f'"{shown}"' if " " in shown or "\n" in a else shown)
    return " ".join(parts)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cli", required=True, choices=["agy", "grok", "codex"])
    p.add_argument("--brief", required=True, type=Path,
                   help="path to the self-contained brief (a file, never inline text)")
    p.add_argument("--task-name", default="", help="short name; used for the branch")
    p.add_argument("--mode", default="write", choices=["read", "write"])
    p.add_argument("--model", default="", help="omit to use the CLI's own default")
    p.add_argument("--max-turns", type=int, default=0, help="grok only")
    p.add_argument("--timeout", type=int, default=0, help="seconds; 0 = no cap")
    p.add_argument("--repo", type=Path, default=Path.cwd())
    p.add_argument("--no-worktree", action="store_true",
                   help="run in the repo itself; only for --mode read")
    p.add_argument("--keep-worktree", action="store_true",
                   help="keep the worktree a dry run created")
    p.add_argument("--unsandboxed", action="store_true",
                   help="drop the CLI's sandbox. codex and agy currently cannot "
                        "read a file on this machine without it; the worktree "
                        "becomes the only containment")
    args = p.parse_args()

    if not args.brief.is_file():
        print(f"error: brief not found: {args.brief}", file=sys.stderr)
        return 2
    if args.no_worktree and args.mode == "write":
        print("error: --no-worktree with --mode write would let the delegate edit "
              "the shared tree. Refusing.", file=sys.stderr)
        return 2
    if args.no_worktree and args.unsandboxed:
        print("error: --unsandboxed with --no-worktree is an unsandboxed agent "
              "loose in a tree other sessions share. Refusing.", file=sys.stderr)
        return 2
    if args.max_turns and args.cli != "grok":
        print(f"note: --max-turns is a grok flag; {args.cli} has no turn cap.",
              file=sys.stderr)
    if not shutil.which(args.cli):
        print(f"error: {args.cli} is not on PATH", file=sys.stderr)
        return 127

    dryrun = os.environ.get("DELEGATE_DRYRUN") == "1"
    repo = Path(git("rev-parse", "--show-toplevel", cwd=args.repo))
    slug = slugify(args.task_name or args.brief.stem)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    run_dir = RUNS_DIR / f"{stamp}-{args.cli}-{slug}"
    run_dir.mkdir(parents=True, exist_ok=True)
    args._last_message = run_dir / "last-message.txt"

    branch = f"delegate/{slug}-{stamp}"
    if args.no_worktree:
        workdir, worktree = repo, None
    else:
        # Inside the run dir, so one directory holds the whole run: the
        # worktree, the logs and result.json. Nothing is left beside the repo.
        worktree = run_dir / "tree"
        git("worktree", "add", "-b", branch, str(worktree), "HEAD", cwd=repo)
        workdir = worktree

    argv = build_argv(args.cli, args.mode, args.brief, workdir, args)

    # The announce line: what runs, on whose quota, under what cap, and where.
    cap = []
    if args.max_turns and args.cli == "grok":
        cap.append(f"{args.max_turns} turns")
    if args.timeout:
        cap.append(f"{args.timeout}s")
    sandbox_note = ""
    if args.unsandboxed and UNSANDBOXED_FLAGS[args.cli]:
        sandbox_note = " / SANDBOX OFF, worktree is the only containment"
    elif args.cli in ("codex", "agy") and not args.unsandboxed:
        print(f"note: {args.cli} denies all file access on this machine without "
              "--unsandboxed; expect an empty answer. See `codex doctor`.",
              file=sys.stderr)
    print(
        f"-> {args.cli} / {args.model or 'CLI default model'} / "
        f"{QUOTA[args.cli]} quota / {', '.join(cap) or 'no cap set'} / "
        f"{args.mode}-mode{sandbox_note} / {workdir}",
        file=sys.stderr,
    )

    result = {
        "contract": "delegate.result.v1",
        "cli": args.cli,
        "model": args.model or None,
        "quota": QUOTA[args.cli],
        "mode": args.mode,
        "brief": str(args.brief),
        "worktree": str(worktree) if worktree else None,
        "branch": branch if worktree else None,
        "run_dir": str(run_dir),
        "command": display(argv),
    }

    if dryrun:
        result["status"] = "dryrun"
        print(f"DRY RUN -- would execute:\n  {display(argv)}", file=sys.stderr)
        if worktree and not args.keep_worktree:
            git("worktree", "remove", "--force", str(worktree), cwd=repo)
            git("branch", "-D", branch, cwd=repo)
            result["worktree"] = None
            print("dry run cleaned up its worktree "
                  "(--keep-worktree to inspect it)", file=sys.stderr)
        (run_dir / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0

    stdin_text = args.brief.read_text(encoding="utf-8") if args.cli == "codex" else None
    started = time.monotonic()
    try:
        proc = subprocess.run(
            argv,
            cwd=str(workdir),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=args.timeout or None,
        )
        status, exit_code = ("ok" if proc.returncode == 0 else "failed"), proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as exc:
        status, exit_code = "timeout", None
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + f"\n[delegate] killed after {args.timeout}s"
    except FileNotFoundError:
        git("worktree", "remove", "--force", str(worktree), cwd=repo) if worktree else None
        print(f"error: {args.cli} is not on PATH", file=sys.stderr)
        return 127

    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", "replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode("utf-8", "replace")

    (run_dir / "stdout.txt").write_text(stdout, encoding="utf-8")
    (run_dir / "stderr.txt").write_text(stderr, encoding="utf-8")

    porcelain = git("status", "--porcelain", cwd=workdir)
    result.update(
        status=status,
        exit_code=exit_code,
        duration_s=round(time.monotonic() - started, 1),
        files_touched=[line[3:] for line in porcelain.splitlines() if line],
        spend=extract_spend(args.cli, stdout),
        stdout_path=str(run_dir / "stdout.txt"),
        stderr_path=str(run_dir / "stderr.txt"),
        last_message_path=str(args._last_message) if args._last_message.exists() else None,
    )
    (run_dir / "result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")

    # An unsandboxed read-mode run has nothing enforcing read-only, so check
    # after the fact rather than trusting a flag that was not applied.
    if args.mode == "read" and result["files_touched"]:
        result["status"] = status = "write-violation"
        (run_dir / "result.json").write_text(
            json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nWARNING: a read-mode delegate wrote "
              f"{len(result['files_touched'])} file(s). Discard this worktree "
              f"rather than merging it.", file=sys.stderr)

    print(json.dumps(result, indent=2))
    if result["files_touched"]:
        print(f"\nreview: git -C {workdir} diff", file=sys.stderr)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
