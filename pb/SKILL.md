---
name: pb
description: Use when a website has to be driven interactively on this machine - clicking through a shop, filling a checkout or booking form, logging in, searching a site with its own form, any multi-step flow on a page whose structure is not known yet - and especially when a card has to be entered. Also general browsing that needs a real browser - reading search results and listings as records, scrolling endless lists, hover menus, suggestion lists, uploads, downloads, drag and drop, JS dialogs, tables, PDFs and pages curl cannot read. `pb` keeps one Patchright Chrome open and takes short shell commands, so there is no write-script, run, fix, rerun loop. Fastest and most reliable driver in the 2026-11 benchmark (a blind checkout in about 1.5 min, vs 14 min for one-shot scripts), exercised on 50 large shops, on 94 browsing tasks across 41 sites and on 28 literature-research tasks (PubMed, PMC, ClinicalTrials.gov, Europe PMC, journals). Not for plain reads (use curl_cffi) or recurring jobs with known selectors (use a CDP script).
---

# pb: a browser that stays open between commands

`pb` is on PATH (`~/bin/pb`, code in `~/.claude/skills/pb/`). It runs a small daemon holding one Patchright Chrome
(real Chrome, headful, persistent profile), and every command returns a short observation of what changed.
Tell Javier you are using pb (Patchright) and why before starting.

This is the fourth build (2026-11-16): built on a sweep of 50 shops, then extended and fixed for general browsing on
94 tasks across 41 sites. Development, tests and measurements live in `~/Code/buy/browserbench` (`tools/pb.py`,
`tools/pb`, `tests/test_pb.py`, `REPORT.md`). Copy a new build here (both `pb` and `pb.py`) only after it passes
`python -I tests/test_pb.py` and `bash tools/live_checks.sh`.

## Start

```
pb start --profile NAME URL          # profile dir ~/.patchright-NAME, reused across runs (keeps logins and bot trust)
pb start --profile NAME --secrets FILE URL   # FILE defaults to ~/Code/payments.env
```

One session per working directory; `pb -s NAME ...` or `PB_SESSION=NAME` picks another. Use one profile per site.
Big retailers show a human check to a brand-new profile, often right after the first search: reuse the site's
existing `~/.patchright-<site>` profile. PubMed's web search shows a reCAPTCHA to a new profile (4 of 4 runs,
2026-11-17): for literature use NCBI E-utilities or the Europe PMC REST API with curl, and pb for PMC, Europe PMC,
ClinicalTrials.gov and journal pages, which read fine.
The window opens at least 1366 wide, so sites serve their desktop layout (`--window WxH` for another size,
`--headless` for no window; it sends the same user agent as a window, but a window still gets through more walls).
Never run `out=$(pb start ...)`: the daemon inherits the pipe. Redirect to a file or run it plainly.

## Commands

TARGET is a ref from an answer (`e12`), visible text (`"Add to Cart"`), a field's label, placeholder or name,
`id=X` or `name=X` as the view prints them, or `css=SELECTOR` (frames are searched too; a target that reads as a
CSS selector is tried as one when no text matches, and the answer says so). A control whose name holds the words
only in the middle of other words, or a toggle, is not clicked for a text target: use its ref. Quote a target or a selector that has spaces. `pb help` prints everything.

### Look

- `pb open URL` navigate and print the view
- `pb view` interactive elements with refs, an open dialog first. `--all` adds every header and footer link,
  `--grep REGEX` filters (a matching heading keeps the lines under it and is printed even with nothing under it;
  matches ignore case). A run of numbered controls (calendar days,
  line numbers, pages) is one line, `e79..e108 30 buttons "1".."30" under "December 2026"`, and the line says how
  to pick one: by its date in any common form (`pb click "January 15, 2027"`, `"Jan 15 2027"`, `"2027-01-15"`),
  with `pb click 15 --near "December 2026"`, or by a ref in the range (refs run in day order). This works for days
  that show a price and for two months side by side. When that month is not shown, the answer says which is: press
  the calendar's Next button first
- `pb find TEXT` elements whose text or label matches; a link shows its address (`-> URL`)
- `pb text REGEX` page text lines matching REGEX, in page order, each with the line before and after (`--context N`
  for up to 5; the count comes first). A matching line is shown whole up to 3000 characters, a longer one as the
  sentences around the match. `pb text` alone prints the page text, capped (`--from N` continues). Every
  frame that shows is read (`[frame NAME]`); a JSON, text or XML address is printed as it is; a PDF is read with
  pdftotext, also a PDF or text file opened by its `file:` address. After any command that saved a PDF (a link that
  downloads, `pb open` or `pb tab new` of a PDF address, `pb download URL PATH`), the next `pb text` reads that
  file, once, and its first line says so. The same file downloaded again is not saved twice.
  On a page pb flagged as a human check, reading commands say so first
- `pb text --headings` (or `pb outline`) the page's own headings with their levels, indented; those of the header,
  menus, side boxes and footer, and collapsed ones, are counted, not listed
- `pb text --section HEADING [--nth K]` the text under one heading. Of several headings by that name the higher
  level, then the longer section, comes first; the answer says how many there are. A heading in a collapsed part
  is read from what is loaded, and the answer names the button that expands it. `pb text --of TARGET` one
  element's whole text plus its href, value, datetime, title, aria-label, alt, src
- `pb items [REGEX] [--n N] [--from K]` the page's repeated cards or rows (search results, listings, feeds) as
  records `#1`, `#2`...: their text pieces joined by ` | `, then `-> eNN URL`, the main link (`pb click eNN` opens
  it; a long link is shortened). The first line names the group it chose and only the others that could be the
  list meant. On a page with no result list (an error or empty state) it says so and quotes the page's message. It prefers the list the page marks as results or that holds the words searched for, and
  joins a list split in pieces; `--in "HEADING"` takes the list under that heading, `--in GROUP` (or a ref, selector or
  text inside the group you want) another group. Ads say "Sponsored", also ones the page marks only in markup. Use it before writing `pb eval` with
  site selectors
- `pb table` lists the page's tables; `pb table N|TEXT [--rows A-B]` prints one as rows of cells joined by ` | `
  (TEXT: caption, header, the heading above, or a cell's text; the answer starts a little before that row)
- `pb links [REGEX]` links with their addresses (text or address matching), count first, 40 at most
- `pb scroll down|up [N]`, `pb scroll top|bottom`, `pb scroll TARGET` (also plain text). The answer says where the
  page is and what is in view; `scroll bottom` keeps going while an endless list loads more (15 rounds at most)
- `pb shot [--full] [TARGET] [PATH.png]` the window, the whole page or one element, card fields painted over

### Act

- `pb click TARGET`. With many identical buttons add `--near`: `pb click Select --near "12 Main St"`. It refuses,
  and clicks nothing, when no single match is next to that text (in a calendar: `pb scroll "January 2027"` first).
  `--nth N` (also for fill, select, check) takes the Nth of equal matches in page order when `--near` cannot tell
  them apart (three Delete buttons side by side).
  `--right` and `--double` for context menus and double-click handlers. A disabled button is refused with the
  reason; a ref the page has re-rendered is found again by itself; plain text that reacts to clicks (a sortable
  table header) is clicked when no control matches. A button wins over a text box with the same label or
  placeholder; a click on a control whose name only contains the words says so in a NOTE
- `pb fill TARGET VALUE` (ref, label, placeholder or name; a field with no label of its own is found by the text
  next to it, and the answer says so). Also sliders and date, time, month and color fields ("12/25/2026",
  "Dec 25, 2026", "3:30 PM"); on a dropdown it selects, on a file field it uploads. A hidden, disabled or read-only
  field fails at once with the reason, and so does a date the page throws away after typing (then pick the day in
  the calendar). A typed date is entered by leaving the field (Tab); a calendar the fill left open is closed with
  Escape, or a NOTE names its close button
- `pb fill TARGET VALUE --pick [TEXT]` a field with a suggestion list: see rule 5
- `pb select TARGET OPTION` (a US state by name or code; `pb select TARGET "A" "B"` for a multi-select; a radio
  group under that legend is ticked; on a text-box dropdown it types the option and picks it, as `--pick` does),
  `pb check TARGET`, `pb uncheck TARGET` (TARGET may be the text of the row or list item that holds the one box)
- `pb press KEY` (`Enter`, `Escape`, `ctrl+a`, `shift+Tab`...), `pb type TEXT`
- `pb hover TARGET` the menu, tooltip or caption it opens is in the answer (also inside a batch) and stays open for
  the next step:
  `pb do 'hover Products; hover More; click Archive'`
- `pb drag SOURCE TARGET`. `pb upload TARGET FILE...` (the file field, or the button that opens the file chooser;
  relative paths start in your directory). `pb download TARGET|URL [PATH]` saves what a link points to with the
  browser's cookies; a download that any action starts is saved too (`DOWNLOAD saved PATH (N bytes)`)
- `pb dialog accept [TEXT] | dismiss` what to do with a JS alert, confirm or prompt (default: accept) that comes
  during the rest of the `pb do` batch, or, given as a command of its own, during the next command only:
  `pb do 'dialog dismiss; click Delete'`. Every dialog is reported in a NOTE
- `pb do 'cmd; cmd; cmd'` several commands in one call, one observation at the end. Steps may cross page loads,
  because each step waits for its target: `pb do 'click "Checkout"; fill "Email" a@b.c; click Continue'`.
  Put `try` before a step that may not apply (`try click "No thanks"`): it is skipped when its target is not there.
  Steps are pb commands without the word `pb`
- `pb wait TEXT`, `pb wait --gone TEXT` (`--timeout SECONDS`, default 20): only after a `still loading` NOTE, or
  to act the moment something shows: `pb do 'wait "75%"; click Stop'` (it looks every 50 ms and the next step starts
  at once; in a batch it waits for the text to show up anew, not for words the page had when the batch began).
  `pb wait TEXT --in TARGET` waits for the text inside one element: `pb wait "75%" --in id=progressBar`. A plain
  `pb wait` that finds the text already on the page ends at once and says so

### Checkout

- `pb card [SECTION]` types card number, expiry (also month and year dropdowns), CVV and cardholder name from the
  secrets file into the page's card fields, payment iframes included. Prints ok flags only, and exits 1 with
  `CARD INCOMPLETE` when a part did not go in or a field lost its content (it types such a field once more, slowly,
  first; when it finds no card field at all it names what may open the card form). SECTION is a card in the secrets file
  (`card1`, `card2`), never a field on the page. `pb secret TARGET KEY` types or selects one secret (card.number,
  card.exp, card.cvc, card.name, buyer.email, buyer.phone)
- `pb review` what the page says about the order: the final button, pickup or shipping, every money line, every
  checkbox, what is filled in, what is wrong. pb prints it unasked when the final button becomes enabled
- `pb expect` checks the page against the request in code, one PASS or FAIL line per check, exit code 1 on a failure:
  `pb expect 'GEARUP15' --in 'Pickup' '196 Somerville Ave' --in 'Summary' 'Order Total $29.79' --not 'Keene' --unchecked 'create an account' --enabled 'Place Order'`.
  A bare text must be in the page text or in a visible field (the line says where); `--in SECTION TEXT` must be in
  the block under the heading or label that best matches SECTION (equal, then starting with it, then containing
  it; the answer names the block). `--unchecked` and `--disabled` also pass when the box or button is not on the
  page, and say so. Use single quotes: inside double quotes the shell eats `$29`

### Other

- `pb eval 'JS'` prints the result as JSON (objects need no `JSON.stringify`); `pb eval -r 'JS'` prints a string as
  it is. `pb py FILE` or `pb py -c CODE` runs async Python against the page (`return await page.title()`)
- `pb tabs`, `pb tab N` (tabs count from 0), `pb tab new [URL]` (an address that downloads is saved and the blank
  tab closed), `pb tab close [N]`, `pb back`, `pb forward`, `pb reload`,
  `pb window [WxH]` (`pb window 420x900` shows the phone layout), `pb status`, `pb stop` (answers once the browser is closed)
- `pb recover` when a command says the page froze: reopens the same URL in a new tab

## Reading a page

`pb view` lists controls, not content. To get facts off a page take the narrowest of: `pb items` for a list of
results, `pb table` for tabular data, `pb text REGEX` for a known word, `pb text --section` for one part of an
article (`pb outline` first on a long one), `pb text --of TARGET` or `pb links REGEX` for an address or an
attribute, and `pb eval` last.

## Output

`+` lines are elements or text that appeared after the action, `!` lines are alerts or errors shown by the page.
After a page change the answer starts with `URL ->`. After a big change it lists the first 25 new lines and counts
the rest; after a click, back, forward or tab to another page, its main heading and first text lines, then 25
lines without the header's and footer's controls, and a count (`pb view` prints it all). A batch that ends by
reading answers with what it read, not with the earlier page change. A view of a page with almost no controls shows its first text
lines. A command refuses an option it does not have and lists its options; a pattern that starts with a dash goes
after `--`. A browser check that only says it is checking ("Checking your browser", "Just a moment") gets up to
12 s to pass by itself (`NOTE a browser check ... passed by itself`); one with something to do is a human check at
once, and the answer's first line then starts with `HUMAN CHECK:` (never together with "passed").
`NOTE` lines say what else happened: the site refused a submission (`POST /cart -> HTTP 403`; a failed background
request is named only when nothing visible happened), a dialog
opened, a JS dialog and what pb did with it, the page looks like a sign-in wall, a human check, a new tab, an
error status (`HTTP 404`), a PDF or JSON document, a plain-HTTP site, or the answer was written while the page was
still loading. Output is already short and ordered by importance: do not pipe pb through `head`, `tail` or `grep`
(you lose lines); narrow with `--grep` or `pb text REGEX`.

Answers that ask for a step from you:

- `covered by the dialog "...", so nothing was clicked`: click the close button it names, then repeat the step
  (a dialog that stays open after its Close: `pb press Escape`)
- `still loading: the page shows "Loading..."`: `pb wait "TEXT YOU EXPECT" --timeout 30`
- `suggestions open:` after a fill: choose with `pb click "ENTRY"`, or redo the fill with `--pick`
- `asks for a login (HTTP 401)`: put the user and password in the address, `https://USER:PASSWORD@host/...`
- `order changed` after a click on a table header or a drag: the same lines, in a new order

## Speed

- Do not add `pb wait` or sleeps. Every command waits until its effects are in (requests answered, loading signs
  gone, page stopped changing), and a command that names a target waits for it while the page is still loading.
  After a "still loading" NOTE no extra `pb view` is needed unless the control you want is missing.
- Put several steps in one `pb do`, also across page loads. Fewer calls is where the time goes.
- A failed step in a `pb do` stops the batch and exits 1; the answer says which step, how many ran and how many
  did not: run the rest again after fixing that step. A human check stops it with `ERR at step ...: HUMAN CHECK`.
- Dismiss a cookie banner first: it covers buttons, and pb then has to click through it by script.

## Rules

1. **Card data never enters your context.** Only `pb card` / `pb secret` touch the secrets file. Never read it,
   never put a card number in a command, never `pb eval` a card field's value. pb also replaces card numbers (and
   the CVV and expiry where a field value shows) in everything it prints or logs, and paints card fields over in
   screenshots; that is a safety net, not a licence to go looking. pb types no card data on a plain-HTTP page.
2. **Never click the final pay / place-order button without Javier's yes in this session.** Stop with the button
   enabled, show him the read-back below, wait. Amazon is the one exception he has stated (his "buy it" after the
   summary is enough). A "Continue" or "Review order" button on the payment step may already check the card with
   the bank: that is not placing the order, but say so when you report. The same goes for anything else that
   cannot be undone: sending a message, submitting a form to someone, deleting.
3. **Read the order back in code before saying "ready".** A driver's own "ready" is not proof: in the benchmark two
   runs reported the right store while the cart was on another one. On the final page run `pb expect` with every
   fact the request fixes (item, quantity, store or address under its section, total, promo, boxes that must be off,
   the final button enabled) and report ready only when every check passes. Show Javier the review lines, not what
   you intended. Then `pb shot PATH` and look at the screenshot.
4. **Change store, date or other options before adding to cart**, then check the cart shows them. Carts often keep
   what was selected at the moment of adding.
5. **Suggestion lists (autocomplete):** `pb fill FIELD "VALUE" --pick "ENTRY TEXT"` (`--pick` alone takes the entry
   that matches VALUE, `--pick 1` the first). It types, waits for the list, picks the entry (with the keyboard where
   the list shows which entry is highlighted, else by click) and prints what the field then holds. On exit 1 it
   lists the suggestions it saw: pick one of those. A code the page takes with no list ("BOS") is ok; on a field
  that already shows a chosen value as a box ("From BOS Boston..."), pb opens the box itself. Do not use `press ArrowDown; press Enter` yourself: it takes the
   wrong entry when the first one is already highlighted. In a checkout address form you may also ignore the list
   and fill the fields one by one. When a list covers a click target pb closes it, and if it will not close pb
   sends the click to the target by script and says so.
6. **A human check or block page is a stop.** pb flags it (`HUMAN CHECK`). Do not retry, reload in a loop or try to
   get around it: tell Javier, and leave the browser open if he may want to solve it himself.
7. `CARD INCOMPLETE` means the card is not fully in: fix that field (`pb secret TARGET card.exp`...) or stop. Never
   continue on the assumption that it probably worked.
8. If another session may be using the same profile, use your own profile. Leave the browser open when a human has
   to finish (3DS, a human check); otherwise `pb stop` when done.
9. **Plain-HTTP sites** open (Chrome's own warning is off in pb's profiles) and are named in a NOTE. Do not type a
   password on one.
10. **pb's profiles have no iCloud Passwords.** A login whose password lives in iCloud Keychain is filled in the main
   Chrome with the `icloud-passwords` skill (`icloud.py pick USERNAME`), which also unlocks the extension when it
   asks for a code. Never ask Javier to RDP in to read that code.

A Haiku or Sonnet subagent at medium effort is enough to drive pb; give it this skill's command list and the rules,
and check its result yourself with `pb review` / `pb expect` (or `pb text`, `pb items` for a read) before you report.

## What the sweeps showed (2026-11-16)

Guest checkout with a fresh profile on 50 shops: about a third stop a new profile with a human check (Walmart,
Target, Temu, Home Depot, Wayfair and others), several require an account or membership (Amazon, Costco, Kroger,
Gap, H&M), and some validate the buyer's phone, address or email hard. None of that is pb's to solve. Where the
shop lets a guest through, pb reaches the card step in about 3 to 6 minutes on a site it has never seen.

General browsing with a fresh profile on 41 sites (94 tasks: reading, searching, forms, uploads, downloads, dialogs,
frames, date pickers, suggestion lists): 92 done right in the second run, about a minute and a half per site with a
Haiku driver. What stopped a fresh profile: Reddit (a human check on the first page), Amtrak's fare search in one
of two runs (HTTP 403 on the search request), and sec.gov after repeated automated visits (its "undeclared
automated tool" page). Stack Overflow shows a challenge page that passes by itself.

## When something is slow or odd

`~/.pb/SESSION.timing.jsonl` records every request with where its time went (page scans, waits and why each wait
ended, actions). `python -I ~/Code/buy/browserbench/tools/timing_dump.py latest` prints it. Start the daemon with
`PB_TRACE=1` to also log which requests each long wait was waiting for (`tools/trace_dump.py`) and which calls were
left out of the wait (`left out:` notes: an answer that came too early will name the call there).
`PB_HOME=DIR` makes the installed client run the `pb.py` in DIR, to try a development build without installing it.
