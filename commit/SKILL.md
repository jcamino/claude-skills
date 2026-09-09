---
name: commit
description: Use when committing or pushing work on this machine, where several Claude sessions share one working tree — including when the tree is dirty with work you did not write, when a commit you did not make has appeared, or when a builder has swept another session's files into your build output.
---

# Commit

**You stage the exact paths you edited. Nothing else, ever.**

The working tree is shared. Anything dirty that you did not write belongs to another
session, to Javier, or to a builder that ran behind you — staging it silently steals it
into your commit. `git add -A`, `git add .`, `git commit -a` and `git add <dir>/` cannot
tell your work from theirs, so they are never correct here.

Do the git work yourself. Never hand Javier a command to run.

## Before you start editing

Keep a running list of every path you write to this session. That list is the only
thing you are allowed to stage. If you did not record it, you cannot commit it —
re-derive it by re-reading the transcript, not by trusting `git status`.

## The sequence

1. **Survey.** `git status --porcelain` and `git log --oneline -5`.
2. **Report the delta, then keep going.** Name every dirty path that is NOT on your
   list, and every commit on top of the base you started from: "3 files dirty that I
   did not touch: X, Y, Z — leaving them." A foreign commit or a foreign dirty file is
   the *normal* state of this tree; naming it is the requirement, stopping is not.
   Stop and ask only when it **overlaps your work** — a foreign commit that touched a
   path on your list, or a dirty foreign version of a file you also edited. Javier is
   usually unreachable mid-task; when nothing overlaps, say what you found and finish
   the job.
3. **Confirm the paths are in this repo.** `git ls-files --error-unmatch <path>` for
   tracked files, or check `git rev-parse --show-toplevel` contains them. A path
   outside the repo means you edited the wrong copy — a common failure when a
   worktree is in play.
4. **Check line endings.** `git ls-files --eol <paths>` — every file must be `w/lf`.
   A `w/crlf` means `core.autocrlf` or a pwsh redirect got at it; fix it before
   committing, not after.
5. **Stage explicitly.** `git add -- <path1> <path2> ...` with the literal paths
   from your list. Then `git diff --cached --stat` and show it.
6. **Commit.** Conventional message, and end it with the attribution lines from this
   session's system-reminder.
7. **Push** only if the branch already tracks a remote and Javier asked for it.
   Otherwise report the commit and stop.

## Generated files and builders

Builders read the working tree, not git. In a shared tree that means the builder
bundles whatever another session left lying around, and your build output stops being
a function of the commit you are about to make.

Before staging built output, diff it and look for symbols from files that are not on
your list. If someone else's uncommitted work is in there, you have two safe moves:

- **Leave the output uncommitted.** Commit the sources, say in the message that the
  artifact needs a rebuild once the tree is clean. Always available.
- **Build in a clean worktree.** `git worktree add ../<name> HEAD`, apply your edits
  there, build, commit, `git merge --ff-only` back, remove the worktree.

**Never `git stash`, `git checkout --`, `git restore`, or move a path you did not
write.** Not even temporarily, not even if you put it back afterwards — the other
session is live, and its next write lands in the window you opened. A stash you fail
to pop is silent data loss. Clearing someone else's work out of your way is not your
call; build around it instead.

If a path you are staging is built output, its source must be in the same commit and
the build must have been run by the current builder. Confirm the builder is the
current one before running it — a stale build script silently reverts newer work,
which is the one clobber that has actually happened here.

## Branch integration

Prefer linear history. A feature branch whose base has not moved gets fast-forwarded
or rebased — never `git merge --no-ff` on these local, single-user repos, which just
adds a noise merge commit. Merge commits are for genuinely diverged histories only.

## Quick reference

| Situation | Command |
|---|---|
| What changed | `git status --porcelain` |
| Who else committed | `git log --oneline -5` |
| Path really in repo | `git ls-files --error-unmatch <path>` |
| Line endings | `git ls-files --eol <paths>` |
| Stage | `git add -- <paths>` |
| Verify staged | `git diff --cached --stat` |
| Unstage a mistake | `git restore --staged -- <path>` |
| Build away from the mess | `git worktree add ../<name> HEAD` |

## Rationalizations

| Excuse | Reality |
|---|---|
| "Another session committed — I must stop and ask" | Only if it touched a path on your list. Otherwise name it and finish. Javier is on a call; a blocked task helps nobody. |
| "I'll stash their WIP, build clean, then pop it" | Their session is live. Your pop can conflict, and an unpopped stash is lost work. Build in a worktree. |
| "I'll just restore their file to HEAD for a second" | Same thing, without even a stash to recover from. |
| "It's generated output, committing it is harmless" | Not when the builder swept their unfinished code into it. Diff it first. |
| "The other dirty files are probably mine too" | Your recorded list says otherwise. Trust the list, not `git status`. |
| "Javier can run the build himself when he's back" | You do the git and build work. Report what you could not do, don't delegate it. |

## Red flags — stop

- About to type `git add -A`, `git add .`, `git add <dir>/`, or `git commit -a`
- About to stash, restore, checkout or move a file you did not write
- Staging build output you have not diffed
- Blocking on a question Javier cannot answer, when nothing overlaps your paths
- A commit exists that you did not write and you have not mentioned it
- You are about to tell Javier to run a git command himself

All of these mean: go back to your recorded path list and stage only that.
