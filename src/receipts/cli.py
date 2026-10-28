"""receipts command line.

  receipts new STUDY --title "..."        start a study folder
  receipts run STUDY NAME -r "..." -- CMD ARGS...   run a command and keep its output as evidence
  receipts note STUDY NAME --kind K -r "..." < file  keep a transcript, screen, screenshot... as evidence
  receipts relabel STUDY ID --kind K -r "..."        say what an existing piece of evidence is and shows
  receipts redact STUDY                              replace local paths in existing evidence
  receipts quotes STUDY                   check every quote against its source page
  receipts check STUDY                    refuse claims the evidence doesn't back
  receipts build STUDY [--out DIR]        write receipts.json and receipts.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from . import __version__, build, evidence, ledger, quotes
from .evidence import KINDS, KIND_LABEL

TEMPLATE = '''# receipts ledger. Every claim in the write-up lives here, with what backs it.
# Statuses: tested (cite evidence), documented (cite a source URL), not-found (say where you looked).

[study]
title = "{title}"
date = "{date}"
tester = "Who ran the tests, honestly (e.g. 'I', or 'Claude Code on my Mac')"
platform = "OS and hardware"
not_tested = "Anything you chose not to or couldn't test."

# Local paths in evidence are replaced with these stand-ins before anything is
# saved. Write the real side with ~ so your actual home path is never stored here.
[redact]
"~" = "~"

[[subject]]
id = "tool-a"
name = "Tool A"
version = "x.y.z"
repo = "https://github.com/owner/tool-a"
site = "https://tool-a.example"

[[capability]]
id = "example"
label = "Something a reader would want to know"
[capability.cells]
tool-a = {{ status = "documented", note = "What the docs say.", source = "https://tool-a.example/docs" }}

# A row nobody covers. Every cell must be not-found.
# [[capability]]
# id = "the-gap"
# label = "What none of them do"
# gap = true
# [capability.cells]
# tool-a = {{ status = "not-found", note = "Not in its docs or CLI help.", looked = "docs, --help" }}

# [[quote]]
# text = "the exact words you put in quotation marks"
# url = "https://where.they.appear"

# [[step]]
# title = "What happened"
# sub = "one line of context"
# evidence = ["001"]
# excerpt = "the lines to show, which must appear word for word in evidence 001"
'''


def _study(p: str) -> Path:
    return Path(p).expanduser().resolve()


def cmd_new(a) -> int:
    root = _study(a.study)
    if (root / "ledger.toml").exists():
        print(f"{root}/ledger.toml already exists; not touching it", file=sys.stderr)
        return 1
    (root / "evidence").mkdir(parents=True, exist_ok=True)
    (root / "ledger.toml").write_text(TEMPLATE.format(title=a.title, date=dt.date.today().isoformat()), encoding="utf-8")
    print(f"Started {root}. Edit ledger.toml, then capture evidence with `receipts run`.")
    return 0


def _table(root: Path) -> dict:
    try:
        return ledger.redactions(ledger.load(root))
    except FileNotFoundError:
        return evidence.default_redactions()


def _saved(ev) -> str:
    extra = f"; {ev.meta['redacted']}" if ev.meta.get("redacted") else ""
    return f"saved evidence {ev.id} ({KIND_LABEL[ev.kind]}{extra}): {ev.path}"


def cmd_run(a) -> int:
    argv = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    if not argv:
        print("give the command after --", file=sys.stderr)
        return 2
    root = _study(a.study)
    ev, code = evidence.run(root, a.name, argv, represents=a.represents or "", cwd=a.cwd, echo=not a.quiet, table=_table(root))
    print(f"\n{_saved(ev)} (exit {code})", file=sys.stderr)
    return 0


def cmd_note(a) -> int:
    image = Path(a.file).expanduser() if a.file else None
    if image and not image.is_file():
        print(f"no such file: {image}", file=sys.stderr)
        return 2
    if image and image.suffix.lower() not in evidence.IMAGE_EXT:
        print(f"--file must be an image ({', '.join(evidence.IMAGE_EXT)})", file=sys.stderr)
        return 2
    body = "" if (image and sys.stdin.isatty()) else sys.stdin.read()
    if not body.strip() and not image:
        print("nothing on stdin", file=sys.stderr)
        return 2
    if image and not body.strip():
        body = (a.represents or "") + "\n"
    root = _study(a.study)
    try:
        ev = evidence.note(root, a.name, body, kind=a.kind, represents=a.represents or "", source=a.source or "",
                           image=image, table=_table(root))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(_saved(ev), file=sys.stderr)
    return 0


def cmd_relabel(a) -> int:
    root = _study(a.study)
    evs = evidence.load_all(root)
    eid = f"{int(a.id):03d}" if a.id.isdigit() else a.id
    if eid not in evs:
        print(f"no evidence {eid}", file=sys.stderr)
        return 2
    try:
        ev = evidence.relabel(evs[eid], kind=a.kind, represents=a.represents, table=_table(root))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    print(f"evidence {ev.id}: {KIND_LABEL[ev.kind]}: {ev.represents or '(no description)'}")
    return 0


def cmd_redact(a) -> int:
    root = _study(a.study)
    table = _table(root)
    changed = 0
    for ev in evidence.load_all(root).values():
        before = ev.path.read_text(encoding="utf-8")
        evidence.relabel(ev, table=table)
        changed += ev.path.read_text(encoding="utf-8") != before
    left = [(e.id, p) for e in evidence.load_all(root).values() for p in evidence.find_local_paths(e.body + "\n".join(e.meta.values()))]
    print(f"{changed} evidence file(s) updated with stand-ins: {', '.join(sorted(set(table.values()))) or '(none)'}")
    for eid, p in left:
        print(f"still local in {eid}: {p}  (add it to [redact] in ledger.toml)")
    return 1 if left else 0


def cmd_quotes(a) -> int:
    s = ledger.load(_study(a.study))
    res = quotes.check(s)
    bad = 0
    for r in res:
        mark = "ok   " if r["found"] else "MISS "
        bad += not r["found"]
        print(f"{mark} {r['text'][:70]!r}  {r['url']}" + (f"  ({r['error']})" if r.get("error") else ""))
    print(f"{len(res) - bad}/{len(res)} quotes found on their source pages")
    return 1 if bad else 0


def cmd_check(a) -> int:
    s = ledger.load(_study(a.study))
    probs = ledger.validate(s)
    errs = [p for p in probs if p.level == "error"]
    for p in probs:
        print(p)
    n_cells = sum(len(c.get("cells", {})) for c in s.capabilities)
    print(f"{len(s.subjects)} subjects, {len(s.capabilities)} capabilities ({n_cells} cells), "
          f"{len(s.quotes)} quotes, {len(s.steps)} steps, {len(s.evidence)} evidence files: "
          f"{len(errs)} errors, {len(probs) - len(errs)} warnings")
    return 1 if errs or (a.strict and probs) else 0


def cmd_build(a) -> int:
    s = ledger.load(_study(a.study))
    errs = [p for p in ledger.validate(s) if p.level == "error"]
    if errs and not a.force:
        for p in errs:
            print(p, file=sys.stderr)
        print("not building: fix the errors above (or --force for a draft)", file=sys.stderr)
        return 1
    j, m = build.write(s, Path(a.out) if a.out else None)
    print(f"wrote {j}\nwrote {m}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="receipts", description="Write tool comparisons you can prove.")
    ap.add_argument("--version", action="version", version=f"receipts {__version__}")
    sp = ap.add_subparsers(dest="command", required=True)

    p = sp.add_parser("new", help="start a study folder"); p.add_argument("study"); p.add_argument("--title", required=True); p.set_defaults(f=cmd_new)
    rep = "one sentence: what this evidence shows, e.g. 'OpenRig's queue after the builder handed off'"
    p = sp.add_parser("run", help="run a command and keep its output as evidence")
    p.add_argument("study"); p.add_argument("name"); p.add_argument("-r", "--represents", help=rep)
    p.add_argument("--cwd"); p.add_argument("-q", "--quiet", action="store_true")
    p.add_argument("cmd", nargs=argparse.REMAINDER); p.set_defaults(f=cmd_run)
    kinds = [k for k in KINDS if k != "run"]
    p = sp.add_parser("note", help="keep a transcript, screen, screenshot or other record as evidence")
    p.add_argument("study"); p.add_argument("name")
    p.add_argument("--kind", choices=kinds, default="note", help="; ".join(f"{k}: {KIND_LABEL[k]}" for k in kinds))
    p.add_argument("-r", "--represents", help=rep)
    p.add_argument("--file", help="an image file, for --kind screenshot")
    p.add_argument("--source", help="where it came from, e.g. 'Claude Code transcript, 2026-10-27'"); p.set_defaults(f=cmd_note)
    p = sp.add_parser("relabel", help="set the kind or description of existing evidence")
    p.add_argument("study"); p.add_argument("id"); p.add_argument("--kind", choices=list(KINDS)); p.add_argument("-r", "--represents", help=rep)
    p.set_defaults(f=cmd_relabel)
    p = sp.add_parser("redact", help="replace local paths in existing evidence with the [redact] stand-ins")
    p.add_argument("study"); p.set_defaults(f=cmd_redact)
    p = sp.add_parser("quotes", help="check every quote against its source page"); p.add_argument("study"); p.set_defaults(f=cmd_quotes)
    p = sp.add_parser("check", help="refuse claims the evidence doesn't back")
    p.add_argument("study"); p.add_argument("--strict", action="store_true", help="fail on warnings too"); p.set_defaults(f=cmd_check)
    p = sp.add_parser("build", help="write receipts.json and receipts.md")
    p.add_argument("study"); p.add_argument("--out"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_build)

    a = ap.parse_args(argv)
    try:
        return a.f(a)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
