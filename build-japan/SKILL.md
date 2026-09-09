---
name: build-japan
description: Rebuild japan site pages from markdown and verify
---
1. `git pull && git status` — abort if another session has uncommitted changes to the builder.
2. Edit only markdown under ~/Code/japan/**/*.md (never the built HTML, unless changing design).
3. Run the builder; diff built output against git HEAD and show me the diff.
4. Verify in a real browser (Playwright CLI) at mobile width.
5. Commit only the files touched, then push.