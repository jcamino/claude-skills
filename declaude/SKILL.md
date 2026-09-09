---
name: declaude
description: Use when a page or document written by Claude is about to be published or shared and the user asks to "de-Claude", "declaude", strip AI-sounding prose, or run the copy-editor pass; also when prose has maxims, "not X but Y" pivots, colon reveals, or puffery, or when a list of proposed rewrites is in hand and about to be applied to a page.
---

# Declaude

Copy-editor pass that finds sentences that sound like a language model wrote them and proposes plainer rewrites, using Gemini through the `agy` CLI: **the newest Flash "high" model as the detector, the newest Pro "high" model as the editor.** Facts, numbers, names, quotes and labels are never changed.

## Required output

**Your report contains this table — one row per item in `flash.json` and `pro.json`, including every item you rejected.**

| # | Where | Tell | Verdict | Why |
|---|---|---|---|---|
| 1 | first six words of the paragraph | n | applied | one line |
| 2 | … | n | applied (changed) | what you changed in the model's rewrite and why |
| 3 | … | n | cut | what the paragraph still claims without the sentence |
| 4 | … | n | rejected | which Keep rule it broke |

Every item gets a row. The four verdicts are the only ones: `applied`, `applied (changed)`, `cut`, `rejected`.

Under the table, one line headed **Spotted, not fixed** listing anything wrong with the page that was not on either model's list — or `none`.

## Model rule (non-negotiable)

Always the **latest** Gemini Flash high tier, resolved at run time from `agy models`, never a version typed from memory. `run_declaude.py` does this (`gemini-<max version>-flash-high`, same for `-pro-high`). Typing `gemini-3.7-flash-high` when 3.8 exists is the failure this rule exists for. A version named in a repo note, a changelog or a previous run is memory too — resolve it again.

## Steps

1. Extract the visible text to `copy-for-review.txt` in a fresh work dir (for HTML: `innerText` via the CDP Chrome, not the source).
2. Copy `declaude-prompt.md` from this skill dir beside it and edit the first paragraph so it names the page and its readers; add page-specific tells to the list if you saw any.
3. `python <skill dir>/run_declaude.py <workdir>` (runs from anywhere; paths are made absolute) — resolves models, refuses to run while the prompt still has a `[PLACEHOLDER]`, then runs Flash (detector) and Pro (editor) sequentially with `--add-dir <workdir> --new-project`, absolute paths in the prompt, a nonce, `--print-timeout 12m`, and `--dangerously-skip-permissions` (so agy can read the two files without an interactive prompt; it is given nothing else to touch). Writes `flash.json`, `pro.json`, prints both item lists. `--dry-run` prints the resolved models and commands only; `--only flash|pro` runs one side. Old `*.json` in the workdir are overwritten, so keep one workdir per page version.
4. Review every item yourself and give each one a row in the table above. Take Pro's rewrite when it keeps every fact; use Flash as a checklist. Reject any rewrite that adds a fact, romanises a name, hardens a SECONDARY claim, or edits a table row.
5. Apply with a script whose replacements assert the original string occurs exactly once; re-check tag balance; publish.

## An empty rewrite is a deletion, not a rewrite

When an item's `rewrite` field is empty, the model is asking you to cut the sentence. Before you cut it, read the paragraph without it and write down what the paragraph now claims — that sentence goes in the row's **Why** cell.

If what is left no longer makes the paragraph's point — no reason to prefer one street over the other, no reason the place is worth the trip — the sentence was carrying the argument. Say it plainly instead of cutting it, and mark the row `applied (changed)`.

The judgement lines are what this catches: "the one that matters", "which is the whole of it", "the one worth your time". They are on the tells list because they are usually a knowing aside. When the paragraph offers no other reason for its recommendation, that aside **is** the recommendation, and the tells list is not a licence to delete it.

## Scope: the list, and nothing else

Edit the sentences the two models flagged. Anything else wrong with the page — a line that appears twice, a non-sequitur, a stale price, a dangling callback — goes on the **Spotted, not fixed** line with the text left alone.

A sentence that appears twice is not a duplicate to tidy up; both occurrences stay. Deciding a line is a copy-paste leftover and dropping it is a content edit, and it reaches the page inside a diff the user thinks is a style pass.

## Gotchas (each cost a run)

| Symptom | Cause | Fix |
|---|---|---|
| Output edits a different document | `agy` reads from its remembered workspace, not cwd | `--add-dir <abs dir> --new-project`, absolute paths in the prompt |
| Identical output from two models | `agy` response cache on the prompt string | nonce in the prompt (the script adds one) |
| Empty JSON after 5 min | default `--print-timeout 5m` | `--print-timeout 12m` |
| 35 KB prompt fails | Windows command-line limit | make the model read files from disk (the script does) |

## Common mistakes

- Trusting a model's `original` string to match HTML: tags break matches; match on the text and fall back by hand.
- Judging a rewrite by its length. Longer is fine when the plain version needs the words; padding is not. A fragment restored to a sentence usually grows.
- Running the pass before the content is final; every later edit needs a re-run on the changed paragraphs.
