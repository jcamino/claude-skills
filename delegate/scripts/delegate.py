#!/usr/bin/env python3
"""Dispatch a self-contained brief to agy, grok, codex or omp in its own worktree.

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
    "omp": "depends on model",  # resolved by quota_for()
}

# omp fronts several providers, so unlike the others its quota is a property of
# the model, not the CLI -- and two of its providers are the same quotas agy and
# grok spend. `omp models` lists the current set; these are the prefixes as of
# 2026-09-09. An ollama model runs locally and costs nothing, which makes it the
# right choice for exercising this script without spending anything.
OMP_MODEL_QUOTA = [
    ("gemini", "Antigravity / Google (same quota as agy)"),
    ("claude", "Antigravity / Google (same quota as agy)"),
    ("gpt-oss", "Antigravity / Google (same quota as agy)"),
    ("tab_", "Antigravity / Google (same quota as agy)"),
    ("grok", "xAI (same quota as grok)"),
    ("qwen", "ollama, local — free"),
    ("gemma", "ollama, local — free"),
]


def quota_for(cli: str, model: str) -> str:
    if cli != "omp":
        return QUOTA[cli]
    for prefix, label in OMP_MODEL_QUOTA:
        if model.startswith(prefix):
            return label
    return "unknown provider — check `omp models`" if model else "omp default model"

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
    # omp is the only one of the four with a real read-only mode: --tools is an
    # allow-list, so omitting edit/write/python removes the capability rather
    # than asking the model not to use it. bash is omitted from read mode too --
    # it is a write primitive in disguise.
    "omp": {
        "read": ["--tools", "read,grep,glob"],
        "write": ["--tools", "read,grep,glob,edit,write,bash",
                  "--approval-mode", "yolo"],
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
    "omp": [],  # --tools already gates capability; nothing to bypass
}

# CLIs that are installed but not on PATH. omp lives here and `where omp` finds
# nothing, so shutil.which alone would report it missing.
EXTRA_BIN_PATHS = {
    "omp": [Path.home() / "AppData" / "Local" / "omp" / "omp.exe"],
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
    # Strip newlines only. A bare .strip() eats the leading space of a
    # `git status --porcelain` code (" M file" -> "M file"), which then makes the
    # fixed 3-char slice cut into the filename and report "EADME.md".
    return out.stdout.strip("\r\n")


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

    if cli == "omp":
        # omp takes the brief as an @-prefixed file argument, honours --cwd for
        # real, and --max-time is its own wall-clock cap (the subprocess timeout
        # still backs it up). --no-session keeps delegate runs out of the session
        # picker, since nobody resumes these by hand.
        argv = [exe, "-p", "--mode", "json", "--cwd", str(workdir),
                "--no-session", *perm]
        if args.model:
            argv += ["--model", args.model]
        if args.thinking:
            argv += ["--thinking", args.thinking]
        if args.timeout:
            argv += ["--max-time", str(args.timeout)]
        argv += [f"@{brief}"]
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


SPEND_FIELDS = ("cost_usd", "input_tokens", "output_tokens", "cached_tokens",
                "reasoning_tokens", "total_tokens", "turns")


def _blank_spend() -> dict:
    return {f: None for f in SPEND_FIELDS}


def _jsonl(stdout: str):
    """Yield each parseable JSON object from a JSONL stream, skipping noise."""
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def extract_spend(cli: str, stdout: str) -> dict:
    """Normalise what the CLI reports about the call into one shape.

    Each names its fields differently and two of them stream per-turn usage that
    has to be summed rather than read off the last event, so a multi-turn run is
    not undercounted. Only omp and grok report dollars; codex and agy report
    tokens alone, so cost_usd stays None for those rather than being guessed at.
    """
    spend = _blank_spend()
    try:
        if cli == "grok":
            data = json.loads(stdout)
            usage = data.get("usage") or {}
            spend.update(
                cost_usd=data.get("total_cost_usd"),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cached_tokens=usage.get("cache_read_input_tokens"),
                reasoning_tokens=usage.get("reasoning_tokens"),
                total_tokens=usage.get("total_tokens"),
                turns=data.get("num_turns"),
            )
        elif cli == "agy":
            data = json.loads(stdout)
            usage = data.get("usage") or {}
            spend.update(
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                cached_tokens=usage.get("cache_read_tokens"),
                reasoning_tokens=usage.get("thinking_tokens"),
                total_tokens=usage.get("total_tokens"),
                turns=data.get("num_turns"),
            )
            spend["denied_actions"] = data.get("denied_actions") or []
        elif cli == "codex":
            # One usage block per turn.completed event; sum them.
            totals, turns = {}, 0
            for event in _jsonl(stdout):
                usage = event.get("usage")
                if event.get("type") == "turn.completed" and usage:
                    turns += 1
                    for k, v in usage.items():
                        if isinstance(v, int):
                            totals[k] = totals.get(k, 0) + v
            if totals:
                inp = totals.get("input_tokens", 0)
                out = totals.get("output_tokens", 0)
                spend.update(
                    input_tokens=inp,
                    output_tokens=out,
                    cached_tokens=totals.get("cached_input_tokens"),
                    reasoning_tokens=totals.get("reasoning_output_tokens"),
                    total_tokens=inp + out,
                    turns=turns,
                )
        elif cli == "omp":
            # omp emits JSONL; the terminal line carries every message, and each
            # assistant turn has its own usage + cost. Sum across turns.
            cost = inp = out = cached = reasoning = total = turns = 0
            seen = False
            for event in _jsonl(stdout):
                for msg in event.get("messages") or []:
                    usage = msg.get("usage")
                    if not usage:
                        continue
                    seen = True
                    turns += 1
                    inp += usage.get("input") or 0
                    out += usage.get("output") or 0
                    cached += usage.get("cacheRead") or 0
                    reasoning += usage.get("reasoningTokens") or 0
                    total += usage.get("totalTokens") or 0
                    cost += ((usage.get("cost") or {}).get("total")) or 0
                    spend["provider"] = msg.get("provider")
                    spend["model_used"] = msg.get("model")
            if seen:
                spend.update(cost_usd=round(cost, 6), input_tokens=inp,
                             output_tokens=out, cached_tokens=cached,
                             reasoning_tokens=reasoning, total_tokens=total,
                             turns=turns)
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    return spend


def spend_line(spend: dict) -> str:
    """One-line human summary of a run's cost."""
    if spend.get("total_tokens") is None:
        return "spend: not reported by this CLI"
    bits = [f"{spend['total_tokens']:,} tokens"]
    for label, key in (("in", "input_tokens"), ("out", "output_tokens"),
                       ("cached", "cached_tokens"), ("thinking",
                                                     "reasoning_tokens")):
        if spend.get(key):
            bits.append(f"{spend[key]:,} {label}")
    if spend.get("turns"):
        bits.append(f"{spend['turns']} turn(s)")
    cost = f"${spend['cost_usd']:.4f}" if spend.get("cost_usd") else "cost not reported"
    return f"spend: {cost} / " + ", ".join(bits)


def append_ledger(result: dict) -> Path:
    """Append one line per run to a ledger, so spend is answerable across runs
    and not only for the run in front of you."""
    ledger = RUNS_DIR / "ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    spend = result.get("spend") or {}
    row = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cli": result.get("cli"),
        "model": result.get("model") or spend.get("model_used"),
        "quota": result.get("quota"),
        "mode": result.get("mode"),
        "status": result.get("status"),
        "duration_s": result.get("duration_s"),
        "files_touched": len(result.get("files_touched") or []),
        **{k: spend.get(k) for k in SPEND_FIELDS},
    }
    with ledger.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row) + "\n")
    return ledger


def resolve_exe(name: str) -> str:
    """Absolute path to the CLI. On Windows an npm-installed CLI is a `.CMD`
    shim, which `subprocess` will not find by bare name the way a shell does --
    `grok` resolves for `command -v` and raises FileNotFoundError here. Some are
    not on PATH at all; see EXTRA_BIN_PATHS."""
    found = shutil.which(name)
    if found:
        return found
    for candidate in EXTRA_BIN_PATHS.get(name, []):
        if candidate.is_file():
            return str(candidate)
    raise FileNotFoundError(name)


def display(argv: list[str]) -> str:
    """Readable form of the argv. Paths stay intact so a dry-run command can be
    copied and run; only a genuinely huge argument (agy's inlined brief) is cut."""
    parts = []
    for a in argv:
        shown = a if len(a) <= 200 else a[:197].replace("\n", " ") + "..."
        parts.append(f'"{shown}"' if " " in shown or "\n" in a else shown)
    return " ".join(parts)


def print_ledger_summary() -> int:
    """Totals across every recorded run, grouped by CLI."""
    ledger = RUNS_DIR / "ledger.jsonl"
    if not ledger.is_file():
        print("no delegate runs recorded yet", file=sys.stderr)
        return 0
    rows = [json.loads(l) for l in ledger.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    by_cli: dict[str, dict] = {}
    for row in rows:
        acc = by_cli.setdefault(row.get("cli") or "?",
                                {"runs": 0, "cost_usd": 0.0, "total_tokens": 0,
                                 "unpriced": 0})
        acc["runs"] += 1
        acc["total_tokens"] += row.get("total_tokens") or 0
        if row.get("cost_usd"):
            acc["cost_usd"] += row["cost_usd"]
        elif row.get("total_tokens"):
            acc["unpriced"] += 1

    width = max((len(c) for c in by_cli), default=3)
    print(f"{'cli':<{width}}  {'runs':>4}  {'tokens':>12}  {'cost':>10}")
    grand_cost = grand_tokens = 0.0
    for cli, acc in sorted(by_cli.items()):
        cost = f"${acc['cost_usd']:.4f}" if acc["cost_usd"] else "-"
        if acc["unpriced"]:
            cost += f" (+{acc['unpriced']} unpriced)"
        print(f"{cli:<{width}}  {acc['runs']:>4}  {acc['total_tokens']:>12,}  "
              f"{cost:>10}")
        grand_cost += acc["cost_usd"]
        grand_tokens += acc["total_tokens"]
    print(f"{'all':<{width}}  {len(rows):>4}  {int(grand_tokens):>12,}  "
          f"${grand_cost:.4f}")
    print(f"\n{ledger}", file=sys.stderr)
    return 0


def main() -> int:
    if "--ledger" in sys.argv[1:]:
        return print_ledger_summary()

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger", action="store_true",
                   help="print spend totals across all recorded runs and exit")
    p.add_argument("--cli", required=True,
                   choices=["agy", "grok", "codex", "omp"])
    p.add_argument("--brief", required=True, type=Path,
                   help="path to the self-contained brief (a file, never inline text)")
    p.add_argument("--task-name", default="", help="short name; used for the branch")
    p.add_argument("--mode", default="write", choices=["read", "write"])
    p.add_argument("--model", default="", help="omit to use the CLI's own default")
    p.add_argument("--max-turns", type=int, default=0, help="grok only")
    p.add_argument("--thinking", default="",
                   choices=["", "off", "minimal", "low", "medium", "high",
                            "xhigh", "max", "auto"],
                   help="omp only; reasoning effort")
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
    if args.thinking and args.cli != "omp":
        print(f"note: --thinking is an omp flag; {args.cli} ignores it.",
              file=sys.stderr)
    try:
        resolve_exe(args.cli)
    except FileNotFoundError:
        print(f"error: {args.cli} not found on PATH or in its known install "
              f"location", file=sys.stderr)
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
    quota = quota_for(args.cli, args.model)
    print(
        f"-> {args.cli} / {args.model or 'CLI default model'} / "
        f"{quota} quota / {', '.join(cap) or 'no cap set'} / "
        f"{args.mode}-mode{sandbox_note} / {workdir}",
        file=sys.stderr,
    )

    result = {
        "contract": "delegate.result.v1",
        "cli": args.cli,
        "model": args.model or None,
        "quota": quota,
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

    ledger = append_ledger(result)
    print(json.dumps(result, indent=2))
    print(f"\n{spend_line(result['spend'])}", file=sys.stderr)
    print(f"ledger: {ledger}", file=sys.stderr)
    if result["files_touched"]:
        print(f"review: git -C {workdir} diff", file=sys.stderr)
    return 0 if status == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
