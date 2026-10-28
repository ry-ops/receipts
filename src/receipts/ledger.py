"""The ledger: every claim a write-up makes, and what backs it.

A study is a folder with a ledger.toml and an evidence/ folder. The ledger has:

  [study]         title, date, who ran the tests, on what
  [[subject]]     each tool under test, with the exact version tested
  [[capability]]  one row of the capability map; one cell per subject
  [[quote]]       anything you put in quotation marks, with its source URL
  [[step]]        an ordered replay of a test run, each step tied to evidence
  [redact]        stand-ins for local paths, written with ~ so the real path is
                  never stored, e.g.  "~/Projects" = "~/ry-ops/projects"

Every cell has a status, and each status has a rule:

  tested      you ran it. Must cite evidence ids that exist. An excerpt, if
              given, must appear in that evidence word for word.
  documented  the project says so; you didn't test it. Must cite a source URL.
  not-found   you looked and didn't find it. Must say where you looked.

A capability marked gap = true is a claim that nobody does it, so every cell
in that row must be not-found.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import STATUSES
from .evidence import KINDS, Evidence, default_redactions, find_local_paths, load_all
from .text import contains

LOCK = "quotes.lock.json"


@dataclass
class Problem:
    level: str  # "error" or "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level:7} {self.where}: {self.message}"


@dataclass
class Study:
    root: Path
    data: dict
    evidence: dict[str, Evidence] = field(default_factory=dict)
    lock: dict = field(default_factory=dict)

    @property
    def subjects(self) -> list[dict]:
        return self.data.get("subject", [])

    @property
    def capabilities(self) -> list[dict]:
        return self.data.get("capability", [])

    @property
    def quotes(self) -> list[dict]:
        return self.data.get("quote", [])

    @property
    def steps(self) -> list[dict]:
        return self.data.get("step", [])


def load(root: Path) -> Study:
    root = Path(root)
    path = root / "ledger.toml"
    if not path.is_file():
        raise FileNotFoundError(f"no ledger.toml in {root}")
    with path.open("rb") as f:
        data = tomllib.load(f)
    lock = {}
    if (root / LOCK).is_file():
        lock = json.loads((root / LOCK).read_text(encoding="utf-8"))
    return Study(root, data, load_all(root), lock)


def redactions(s: "Study") -> dict[str, str]:
    """The study's [redact] table with ~ expanded, longest paths first. Falls back
    to showing the home folder as '~'."""
    table = s.data.get("redact")
    if not table:
        return default_redactions()
    out = {}
    for real, stand_in in table.items():
        r = os.path.expanduser(os.path.expandvars(real))
        if r and r not in ("~", "/"):
            out[r] = stand_in
    return out


def quote_key(q: dict) -> str:
    return f"{q.get('url', '')}\n{q.get('text', '')}"


def _ids(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, (str, int)):
        v = [v]
    return [f"{int(x):03d}" if str(x).isdigit() else str(x) for x in v]


def _check_excerpt(s: Study, where: str, ids: list[str], excerpt: str | None, out: list[Problem]) -> None:
    missing = [i for i in ids if i not in s.evidence]
    for i in missing:
        out.append(Problem("error", where, f"evidence {i} does not exist in evidence/"))
    if excerpt and not missing and ids:
        if not any(contains(s.evidence[i].body, excerpt) for i in ids):
            out.append(Problem("error", where, f"excerpt not found word for word in evidence {', '.join(ids)}: {excerpt[:70]!r}"))


def validate(s: Study) -> list[Problem]:
    out: list[Problem] = []
    st = s.data.get("study", {})
    for k in ("title", "date", "tester"):
        if not st.get(k):
            out.append(Problem("error", "[study]", f"missing {k}"))
    if not s.subjects:
        out.append(Problem("error", "[[subject]]", "no subjects"))
    ids = []
    for i, sub in enumerate(s.subjects):
        w = f"subject {sub.get('id', i)}"
        for k in ("id", "name", "version"):
            if not sub.get(k):
                out.append(Problem("error", w, f"missing {k} (say exactly which version you tested)"))
        ids.append(sub.get("id"))
    if len(set(ids)) != len(ids):
        out.append(Problem("error", "[[subject]]", "duplicate subject ids"))

    for cap in s.capabilities:
        cw = f"capability {cap.get('id', cap.get('label', '?'))}"
        if not cap.get("label"):
            out.append(Problem("error", cw, "missing label"))
        cells = cap.get("cells", {})
        for sid in ids:
            c = cells.get(sid)
            w = f"{cw} / {sid}"
            if c is None:
                out.append(Problem("error", w, "no cell: every subject needs a status in every row"))
                continue
            status = c.get("status")
            if status not in STATUSES:
                out.append(Problem("error", w, f"status must be one of {', '.join(STATUSES)}"))
                continue
            if not c.get("note"):
                out.append(Problem("warning", w, "no note: say what you saw"))
            if status == "tested":
                ev = _ids(c.get("evidence"))
                if not ev:
                    out.append(Problem("error", w, "tested without evidence: cite the evidence ids, or mark it documented"))
                _check_excerpt(s, w, ev, c.get("excerpt"), out)
            elif status == "documented":
                if not c.get("source"):
                    out.append(Problem("error", w, "documented without a source URL"))
            elif status == "not-found":
                if not c.get("looked") and not c.get("note"):
                    out.append(Problem("error", w, "not-found without saying where you looked"))
            if cap.get("gap") and status != "not-found":
                out.append(Problem("error", w, "this row is marked as a gap, so it can't be " + status))
        for extra in set(cells) - set(ids):
            out.append(Problem("warning", cw, f"cell for unknown subject {extra}"))

    for i, q in enumerate(s.quotes):
        w = f"quote {i + 1}"
        if not q.get("text") or not q.get("url"):
            out.append(Problem("error", w, "needs text and url"))
            continue
        r = s.lock.get(quote_key(q))
        if r is None:
            out.append(Problem("warning", w, f"not verified yet; run `receipts quotes`: {q['text'][:60]!r}"))
        elif not r.get("found"):
            out.append(Problem("error", w, f"not found at {q['url']} when checked {r.get('checked_at')}: {q['text'][:60]!r}"))

    for eid, ev in s.evidence.items():
        w = f"evidence {eid}"
        if ev.kind not in KINDS:
            out.append(Problem("error", w, f"kind {ev.kind!r} is not one of {', '.join(KINDS)}"))
        if not ev.represents:
            out.append(Problem("warning", w, "no 'represents': say in one sentence what this evidence shows (receipts relabel)"))
        if ev.kind == "screenshot" and ev.image is None:
            out.append(Problem("error", w, "a screenshot with no image file next to it"))
        leaks = find_local_paths(ev.body + "\n" + "\n".join(ev.meta.values()))
        if leaks:
            out.append(Problem("error", w, f"real local path(s) in published evidence: {', '.join(leaks)[:80]} (run `receipts redact`)"))

    for i, stp in enumerate(s.steps):
        w = f"step {i + 1}"
        if not stp.get("title"):
            out.append(Problem("error", w, "missing title"))
        ev = _ids(stp.get("evidence"))
        if not ev:
            out.append(Problem("error", w, "a replay step must cite evidence"))
        _check_excerpt(s, w, ev, stp.get("excerpt"), out)

    return out
