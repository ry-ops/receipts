---
name: receipts
description: Use when writing a comparison, review or "I tried X" post about software tools, or when the user asks for a write-up that must be truthful and evidence-backed. Runs the receipts method: install and run the tools, capture output word for word, label every claim tested / documented / not-found, verify every quote against its live source, and build the figures from the evidence.
---

# receipts: write-ups you can prove

Every sentence in the write-up should be traceable to one of three things: output you captured, a page the project published, or a place you looked and found nothing. The `receipts` CLI enforces that. This skill is the workflow around it.

## Rules that are never relaxed

1. **Tested means you ran it.** A claim is `tested` only if a command in this session produced the output, and that output is saved in `evidence/`. If you only read about it, it is `documented`, with the URL or CLI help it came from.
2. **Not found means you looked.** Say where: docs URL, `--help` output, a schema you searched. "I didn't see it" is not a source.
3. **Quotes are exact.** Anything in quotation marks goes in `[[quote]]` with its URL and passes `receipts quotes`. If a page is behind a bot check, verify it in a browser and say so; never mark it found on faith.
4. **Your own lines are labeled.** If a script you wrote formatted or timed something, mark that line in the evidence as yours (`# (formatted by the test script) ...`). Never present your script's output as the tool's.
5. **Label what each record is and what it shows.** Only `receipts run` produces `kind: run`. Anything else is saved with `receipts note --kind transcript|screen|formatted|screenshot|note` and `-r "<one sentence: what it shows>"`. Never label a copy as a capture.
6. **Don't publish local paths.** Put stand-ins in `[redact]` (written with `~`, e.g. `"~" = "~/ry-ops"`). Evidence headers record that paths were replaced. Changing a path is the only edit allowed to evidence, and it's always disclosed.
7. **Versions and dates on everything.** Each subject has the exact version tested; the study has the date.
8. **Say who did the testing.** If an AI agent ran the tests, the write-up says so.
9. **Gaps are a strong claim.** A row with `gap = true` asserts that none of the subjects do it; every cell must be `not-found` with where you looked.
10. **Ask before touching the user's machine.** Installing tools, changing config files, starting daemons or spending usage credits needs the user's go-ahead. Back up config files the tool will write to before you install it.

## Workflow

```sh
uvx --from git+https://github.com/ry-ops/receipts receipts new studies/<name> --title "<working title>"
```

1. **Scope.** List the subjects and the questions a reader would ask. Put each question in `ledger.toml` as a `[[capability]]` row before testing, so you don't only report what was easy.
2. **Lab.** Make a throwaway repo or directory for the tests. Never test on the user's real projects.
3. **Capture.** Run every meaningful command through `receipts run <study> <name> -r "<what it shows>" -- <cmd>`. For a TUI screen or dialog use `receipts note <study> <name> --kind screen -r "..." < file`. For a screenshot use `--kind screenshot --file shot.png`. For lines copied from your own session log use `--kind transcript`.
4. **Fill the ledger.** One cell per subject per row. Cite evidence ids for `tested`, and add an `excerpt` for the exact lines a reader will see.
5. **Quotes.** Add every quotation, then `receipts quotes <study>`. Fix or drop anything that misses.
6. **Check.** `receipts check <study>` must report 0 errors. Treat warnings as to-dos.
7. **Build.** `receipts build <study>` writes `receipts.json` (for `figures/receipts-figures.js`) and `receipts.md` (the how-this-was-tested box, the capability table, verified quotes and the versions footer).
8. **Write.** Every claim in prose must match its ledger cell. Where the prose says "I saw", the cell says `tested`. Where it says "the docs say", the cell says `documented`.
9. **Clean up.** Remove test daemons, worktrees and test teams you created. Tell the user what you installed and what you left in place.

## Figures

Copy `figures/receipts-figures.{js,css}` next to the post and add:

```html
<div class="rcpt" data-rcpt="matrix" data-src="receipts.json"><p>Text fallback that says the same thing.</p></div>
<div class="rcpt" data-rcpt="replay" data-src="receipts.json"><p>Text fallback.</p></div>
```

The figures read only from `receipts.json`, so they can't claim more than the ledger.
