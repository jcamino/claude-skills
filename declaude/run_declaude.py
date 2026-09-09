#!/usr/bin/env python
"""Declaude runner: newest Gemini Flash high (detector) + newest Pro high (editor) through agy.

usage: python run_declaude.py <workdir> [--dry-run] [--only flash|pro]
<workdir> must contain declaude-prompt.md and copy-for-review.txt.
Writes <workdir>/flash.json and <workdir>/pro.json (agy --output-format json) and prints the items.
"""
import os, re, sys, json, time, subprocess

# The pages under review are full of Japanese; a cp1252 stdout kills the run
# after both models have already been paid for.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AGY = os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe")
if not os.path.exists(AGY):
    AGY = "agy"

def list_models():
    out = subprocess.run([AGY, "models"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
    return [line.split("\t")[0].strip() for line in out.splitlines() if "\t" in line]

def newest(models, family):
    """family 'flash' or 'pro': highest gemini-<ver>-<family>-high by numeric version."""
    best, best_v = None, ()
    for m in models:
        mm = re.match(r"gemini-(\d+(?:\.\d+)*)-%s-high$" % family, m)
        if mm:
            v = tuple(int(x) for x in mm.group(1).split("."))
            if v > best_v:
                best, best_v = m, v
    if not best:
        raise SystemExit("no gemini-*-%s-high model in `agy models`" % family)
    return best

def first_array(text):
    """The first balanced top-level [ ... ] in the response.

    A greedy `\\[.*\\]` swallows the "Left alone" prose the prompt asks for
    after the array, and then fails to parse the lot. Balance the brackets
    instead, ignoring any inside strings.
    """
    start = text.find("[")
    if start < 0:
        return []
    depth, instr, esc = 0, False, False
    for i in range(start, len(text)):
        c = text[i]
        if instr:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    return []


def run(workdir, model, tag, dry):
    wd = os.path.abspath(workdir)
    nonce = "%s-%d" % (tag, int(time.time()))
    prompt = ("Run %s: Read the files %s and %s and do exactly what declaude-prompt.md says. "
              "Output only what it asks for." % (nonce, os.path.join(wd, "declaude-prompt.md"),
                                                 os.path.join(wd, "copy-for-review.txt")))
    cmd = [AGY, "--print", prompt, "--add-dir", wd, "--new-project", "--model", model,
           "--output-format", "json", "--print-timeout", "12m", "--dangerously-skip-permissions"]
    print("[%s] model=%s" % (tag, model))
    if dry:
        print("  " + " ".join('"%s"' % c if " " in c else c for c in cmd)); return None
    out = os.path.join(wd, "%s.json" % tag)
    with open(out, "w", encoding="utf-8") as f, open(os.devnull) as devnull:
        subprocess.run(cmd, stdout=f, stderr=open(out + ".err", "w"), stdin=devnull, cwd=wd)
    try:
        d = json.load(open(out, encoding="utf-8"))
    except Exception as e:
        print("  no JSON (%s); see %s.err" % (e, out)); return None
    r = d.get("response", "")
    print("  status=%s %.0fs" % (d.get("status"), d.get("duration_seconds") or 0))
    items = first_array(r)
    for i, it in enumerate(items, 1):
        print("  #%d [%s/%s] %s" % (i, it.get("tell"), it.get("confidence"), it.get("where", "")[:40]))
        print("    O: %s" % it.get("original", "")[:220])
        print("    R: %s" % it.get("rewrite", "")[:220])
    la = r.find("Left alone")
    if la >= 0:
        print("  " + r[la:la + 600].replace("\n", "\n  "))
    return items

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        raise SystemExit(__doc__)
    workdir = args[0]
    dry = "--dry-run" in sys.argv
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for name in ("declaude-prompt.md", "copy-for-review.txt"):
        if not os.path.exists(os.path.join(workdir, name)):
            raise SystemExit("missing %s in %s" % (name, workdir))
    prompt_text = open(os.path.join(workdir, "declaude-prompt.md"), encoding="utf-8").read()
    if re.search(r"\[[A-Z][A-Z ,'-]{6,}\]", prompt_text):
        raise SystemExit("declaude-prompt.md still has an unfilled [PLACEHOLDER]; describe the page first")
    models = list_models()
    flash, pro = newest(models, "flash"), newest(models, "pro")
    print("resolved: detector=%s editor=%s" % (flash, pro))
    if only in (None, "flash"):
        run(workdir, flash, "flash", dry)
    if only in (None, "pro"):
        run(workdir, pro, "pro", dry)
