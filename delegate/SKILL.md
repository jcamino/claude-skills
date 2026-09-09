---
name: delegate
description: Use when handing a bounded chunk of work to another coding CLI on this machine - omp, agy, grok or codex - instead of doing it in this session. Fits bulk mechanical edits, large read-heavy sweeps, and second-opinion review of a diff or design. Also use to report what delegated work has cost, in tokens or dollars. Triggers include "delegate this", "hand this to codex", "get grok to review it", "run it on omp", "farm this out", "how many tokens did that use", or any task large and mechanical enough that doing it here would burn context for no judgement.
---

# Delegate

**The delegate gets a file, a worktree, and nothing else.** It cannot see this
conversation, it does not share your working tree, and it does not decide what lands.
You write the brief, it does the work in its own worktree, you review the diff and
you own the merge.

Three CLIs are installed and authenticated on this machine. Each bills a different
quota, so which one you pick is a spending decision, not just a quality one.

## When this is worth it

Delegate work that is **large and mechanical**, or that **wants a different model's
eyes**:

- A rename or codemod across dozens of files
- Reading a large tree to answer one narrow question
- Drafting a bulk patch you will then review line by line
- An adversarial second opinion on a design or a diff you already wrote

Do **not** delegate work that needs this conversation's context, work smaller than the
brief it would take to describe, or anything where you would not read the resulting
diff carefully. A delegate that needs three rounds of clarification cost more than
doing it here.

## Routing

Task shape picks the CLI. State the route and the reason out loud before dispatching.

| Task shape | CLI | Why | Suggested model | Write | Read |
|---|---|---|---|---|---|
| Anything needing a **genuinely read-only** delegate, a specific model, or a free run | `omp` | 38 models across 3 providers, real `--cwd`, real `--tools` allow-list, `--max-time`, and the best cost reporting of the four | `gemini-3.8-flash`, or `qwen3-coder:30b` for free | yes | yes |
| Adversarial review, second opinion on a diff or a design | `grok` | Different training, argues back, has `--max-turns`, reports its own dollar cost, and its sandbox works as shipped | CLI default (`grok-4.6-build`) | yes | yes |
| Bulk mechanical implementation, bounded patch drafting | `codex` | Strongest at applying a spec across many files without inventing scope. Needs `--unsandboxed` | CLI default (`gpt-6-astra`) | yes | yes |
| Large read-heavy sweep, bulk analysis, "read all of this and tell me X" | `agy` | Big context, cheap flash models. Needs `--unsandboxed` | `gemini-3.8-flash-medium` | yes | yes |

### Picking an omp model

`omp` is a front-end, not a provider, so **the model decides whose quota you
spend** — and two of its three providers are the same quotas `agy` and `grok`
bill. Routing to omp does not spread load unless you pick the model deliberately.

| Model prefix | Provider | Quota |
|---|---|---|
| `gemini-*`, `claude-*`, `gpt-oss-*` | `google-antigravity` | same as `agy` |
| `grok-*` | `xai-oauth` | same as `grok` |
| `qwen*`, `gemma*` | `ollama` | **local, free** |

Run `omp models` for the current list. An `ollama` model costs nothing, which
makes it the right choice for exercising this script or for bulk work where
quality matters less than volume. The script prints the resolved quota in its
announce line, so a mistake is visible before it is spent.

Override the route when the task obviously wants it, but say why.

### Measured state, 2026-09-09

All three complete a real task; two need `--unsandboxed` to do anything at all.

**codex — needs `--unsandboxed`.** Its Windows sandbox rejects `CreateProcess` for
every shell on this machine, under `-s read-only` and `-s workspace-write` alike,
with `approval_policy="never"` set and no `.rules` file anywhere:

```
Rejected("`\"...\\WindowsApps\\pwsh.exe\" -Command 'type README.md'` rejected: blocked by policy")
```

Removing the WindowsApps alias from `PATH` only moves the failure to
`powershell.exe` 5.1, so it is not the app-alias stub — the sandbox is broken.
`codex doctor` reports "Microsoft Defender can interfere with Codex · exclusions
not verified"; adding those exclusions is the real fix, after which
`--unsandboxed` should stop being necessary. **Containment was verified**: under
`-C <worktree>` with the sandbox off, codex wrote only inside the worktree and
left the main checkout clean.

**agy — needs `--unsandboxed`, and `--add-dir` to find its workspace.** It denies
`RunCommand` under `--mode plan` and `read_file`/`ListDir` under `--sandbox`,
returning an empty response either way; `--dangerously-skip-permissions` fixes
that.

Separately, **agy does not treat the child process's cwd as its workspace.**
Asked to write a file "in your current working directory" it created one in
`~/.gemini/antigravity-cli/scratch` instead — in a git worktree and in a full
`git clone` alike, so this is not about the worktree's `.git` being a file.
`--add-dir <workdir>` is what actually points it at the tree, and with it writes
land correctly even when the brief only says "your current working directory".
The script always passes it. Verified end to end: agy edited `README.md` inside
its worktree and left the main checkout clean.

**grok — works as-is.** Sandboxed, reads correctly, reports what it spent.

**omp — works as-is, and is the only one with real read-only enforcement.**
`--tools` is an allow-list, so `--mode read` removes `edit`/`write`/`bash` as
capabilities rather than asking the model to behave. `--cwd` is honoured for
real (no `--add-dir` needed), the brief goes in as `@<path>`, and `--max-time`
is a genuine wall-clock cap. It is not on `PATH` — the script finds it at
`~/AppData/Local/omp/omp.exe`. Write mode verified: it edited `README.md` inside
its worktree and left the main checkout clean.

Re-check with a dry run and one cheap read-only call before trusting any of this;
these are measurements of one machine on one day, not properties of the tools.

**Never route to `agy --model claude-*`.** `agy` can run Claude Sonnet and Opus.
Delegating Claude work to Claude buys you a second context window and nothing else,
at full price.

## The brief is a file

Write the brief to a file and pass its path. Never inline it into a command string:
on this machine a command string is unescaped once before any shell runs, so `\\`
arrives as `\` and every regex, JSON literal and Windows path in your brief is
silently corrupted. The script reads briefs from disk and builds argv directly for
exactly this reason.

A brief is self-contained or it is useless. The delegate has no chat history, no
memory of what you already ruled out, and no access to what the user said. Include:

- **Goal** — one paragraph, what done looks like
- **Scope** — the exact files or directories in play, and what is off-limits
- **Constraints** — house conventions, the things you already decided not to do
- **Acceptance** — how it will be checked; the command that must pass
- **Output** — what to leave behind: edits, or a written answer, or a diff

## Running it

```bash
python ~/.claude/skills/delegate/scripts/delegate.py \
  --cli codex --brief /path/to/brief.md --task-name rename-foo --mode write
```

| Flag | Meaning |
|---|---|
| `--cli {omp,agy,grok,codex}` | Which delegate |
| `--brief <path>` | The brief file. Required |
| `--task-name <slug>` | Names the branch and the run directory |
| `--mode read` / `--mode write` | `read` = may read and run commands, may not write. **Not** a planning mode — codex's and agy's planning modes deny command execution, and both reach files through commands, so a delegate in one cannot read the tree it was pointed at |
| `--model <id>` | Omit to take the CLI's own default |
| `--max-turns <n>` | `grok` only — the others have no turn cap |
| `--thinking <level>` | `omp` only — `off` through `max`, or `auto` |
| `--timeout <s>` | Wall-clock kill. No cap unless you set one. Also passed to `omp` as `--max-time` and to `agy` as `--print-timeout` |
| `--ledger` | Print spend totals across every recorded run and exit. Takes no other flags |
| `--no-worktree` | Run in the repo itself. Refused with `--mode write` |
| `--unsandboxed` | Drop the CLI's sandbox. Required by codex and agy here; ignored by grok. The worktree becomes the only containment, so never combine it with `--no-worktree` |

Every run creates `git worktree add -b delegate/<slug>-<stamp>` off `HEAD` and runs
the delegate there. One directory holds the whole run —
`~/.claude/delegate-runs/<stamp>-<cli>-<slug>/` — containing `tree/` (the worktree),
`result.json`, `stdout.txt` and `stderr.txt`.

## Spend metrics

Every run records a normalised `spend` block in `result.json` and appends one row
to `~/.claude/delegate-runs/ledger.jsonl`:

```
cost_usd  input_tokens  output_tokens  cached_tokens  reasoning_tokens
total_tokens  turns
```

The four CLIs name these differently and two of them stream **one usage block per
turn**, so the script sums across turns rather than reading the last event — an
8-turn omp run reports 81,908 tokens, not the 10k of its final turn.

| CLI | Dollars | Tokens | Notes |
|---|---|---|---|
| `omp` | yes | full breakdown | also records the provider and the model actually used |
| `grok` | yes | full breakdown | |
| `codex` | no | summed from `turn.completed` events | `cost_usd` stays `null`; never guess it |
| `agy` | no | full breakdown | also records `denied_actions` |

After each run the script prints a one-line summary to stderr. Quote it when you
report back:

```
spend: $0.0650 / 81,908 tokens, 80,708 in, 1,200 out, 914 thinking, 8 turn(s)
```

For the running total across every delegation:

```bash
python ~/.claude/skills/delegate/scripts/delegate.py --ledger
```

```
cli    runs        tokens        cost
agy       1        24,323  - (+1 unpriced)
codex     1        32,258  - (+1 unpriced)
grok      1        51,094     $0.0096
omp       1        11,915     $0.0100
all       4       119,590     $0.0196
```

`unpriced` counts runs that burned tokens on a CLI that does not report cost, so
the dollar column is never mistaken for the whole bill.

Before dispatching, the script prints one line to stderr naming the CLI, the model,
**whose quota it burns**, the cap, and the worktree. Read it. If it says a quota you
did not intend to spend, kill it.

## Dry run first

`DELEGATE_DRYRUN=1` does every local step — resolves the worktree, reads the brief,
builds the exact argv — and stops before the one step that costs tokens. It prints
the command it would have run and cleans up its worktree unless you pass
`--keep-worktree`.

```bash
DELEGATE_DRYRUN=1 python ~/.claude/skills/delegate/scripts/delegate.py \
  --cli grok --brief brief.md --task-name smoke --mode read
```

Dry-run any brief you have not sent before. It is free and it catches the two
failures that actually happen: a brief that did not say enough, and a route to the
wrong quota.

## Landing the work

The delegate never commits and neither does this script. When it returns:

1. Read `result.json` — `status`, `exit_code`, `files_touched`.
2. `git -C <worktree> diff` — read it. All of it. A delegate's diff is a proposal
   from something that could not see the conversation.
3. Run the acceptance command from the brief, yourself, in the worktree.
4. Merge on your terms. Prefer a fast-forward or rebase onto `main`; these are
   local single-user repos and a `--no-ff` merge commit is noise. Use the `commit`
   skill for staging — stage only the paths the delegate touched, which
   `result.json` lists for you.
5. `git worktree remove <path>` and delete the branch when it is merged or rejected.

If the diff is wrong, throw the worktree away and either rewrite the brief or do the
work here. Do not repair a bad delegate diff by hand — that is the expensive path
that made delegating pointless.

## Red flags — stop

- About to pass the brief as an inline string instead of a file
- About to dispatch without saying which quota it spends
- Delegating something you cannot write a self-contained brief for
- Routing to `agy --model claude-opus-*` or `claude-sonnet-*`
- `--mode write` pointed at the shared working tree instead of a worktree
- `--unsandboxed` together with `--no-worktree` — that is an unsandboxed agent
  loose in the tree another session is working in
- Running `agy` without `--add-dir` — its edits go to
  `~/.gemini/antigravity-cli/scratch` and the worktree diff comes back empty
- Merging a delegate's diff you have not read end to end
- Third round-trip with the same delegate on one task — the brief is the problem,
  and you have now spent more than doing it here would have cost
