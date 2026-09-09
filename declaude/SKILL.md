---
name: declaude
description: Use when a page or document written by Claude is about to be published or shared and the user asks to "de-Claude", "declaude", strip AI-sounding prose, or run the copy-editor pass; also when prose has maxims, "not X but Y" pivots, colon reveals, or puffery.
---

# Declaude

Copy-editor pass that finds sentences that sound like a language model wrote them and proposes plainer rewrites, using Gemini through the `agy` CLI: **the newest Flash "high" model as the detector, the newest Pro "high" model as the editor.** Facts, numbers, names, quotes and labels are never changed.

## Model rule (non-negotiable)

Always the **latest** Gemini Flash high tier, resolved at run time from `agy models`, never a version typed from memory. `run_declaude.py` does this (`gemini-<max version>-flash-high`, same for `-pro-high`). Typing `gemini-3.7-flash-high` when 3.8 exists is the failure this rule exists for.

## Steps

1. Extract the visible text to `copy-for-review.txt` in a fresh work dir (for HTML: `innerText` via the CDP Chrome, not the source).
2. Copy `declaude-prompt.md` from this skill dir beside it and edit the first paragraph so it names the page and its readers; add page-specific tells to the list if you saw any.
3. `python <skill dir>/run_declaude.py <workdir>` (runs from anywhere; paths are made absolute) — resolves models, refuses to run while the prompt still has a `[PLACEHOLDER]`, then runs Flash (detector) and Pro (editor) sequentially with `--add-dir <workdir> --new-project`, absolute paths in the prompt, a nonce, `--print-timeout 12m`, and `--dangerously-skip-permissions` (so agy can read the two files without an interactive prompt; it is given nothing else to touch). Writes `flash.json`, `pro.json`, prints both item lists. `--dry-run` prints the resolved models and commands only; `--only flash|pro` runs one side. Old `*.json` in the workdir are overwritten, so keep one workdir per page version.
4. Review every item yourself. Take Pro's rewrite when it keeps every fact; use Flash as a checklist. Reject any rewrite that adds a fact, romanises a name, hardens a SECONDARY claim, or flattens a deliberate device. Keep a judgement line the models flag if it carries the argument; tell the user which ones you kept.
5. Apply with a script whose replacements assert the original string occurs exactly once; re-check tag balance; publish.

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
