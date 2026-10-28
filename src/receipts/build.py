"""Turn a validated ledger into what a write-up needs:

  receipts.json  data for the figures (capability map, replay)
  receipts.md    paste-ready Markdown: the how-this-was-tested box, the
                 capability table, the verified quotes, and the versions footer
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import __version__
from .evidence import KIND_LABEL
from .ledger import Study, _ids, quote_key

LABEL = {"tested": "Tested", "documented": "Documented, not tested", "not-found": "Not found"}
MAX_LINES = 14


def _evidence_index(s: Study) -> dict:
    return {
        eid: {k: v for k, v in {
            "kind": ev.kind, "kind_label": KIND_LABEL.get(ev.kind, ev.kind), "represents": ev.represents or None,
            "image": f"evidence/{ev.image.name}" if ev.image else None, "redacted": ev.meta.get("redacted"),
        }.items() if v}
        for eid, ev in s.evidence.items()
    }


def _step_text(s: Study, stp: dict) -> str:
    if stp.get("excerpt"):
        return stp["excerpt"].rstrip("\n")
    ev = _ids(stp.get("evidence"))
    if not ev or ev[0] not in s.evidence:
        return ""
    if s.evidence[ev[0]].kind == "screenshot":
        return ""  # the image is the evidence; its description is shown separately
    lines = s.evidence[ev[0]].body.rstrip("\n").splitlines()
    return "\n".join(lines[:MAX_LINES] + (["..."] if len(lines) > MAX_LINES else []))


def data(s: Study) -> dict:
    st = s.data.get("study", {})
    return {
        "generated_by": f"receipts {__version__}",
        "study": {k: st.get(k) for k in ("title", "date", "tester", "platform", "not_tested", "url") if st.get(k)},
        "subjects": [{k: sub.get(k) for k in ("id", "name", "version", "repo", "site", "color") if sub.get(k)} for sub in s.subjects],
        "legend": LABEL,
        "capabilities": [
            {
                "id": cap.get("id"), "label": cap.get("label"), "gap": bool(cap.get("gap")),
                "cells": {
                    sid: {k: v for k, v in {
                        "status": c.get("status"), "note": c.get("note"),
                        "evidence": _ids(c.get("evidence")) or None, "source": c.get("source"),
                    }.items() if v}
                    for sid, c in cap.get("cells", {}).items()
                },
            }
            for cap in s.capabilities
        ],
        "evidence": _evidence_index(s),
        "steps": [
            {k: v for k, v in {
                "title": stp.get("title"), "sub": stp.get("sub"), "text": _step_text(s, stp),
                "evidence": _ids(stp.get("evidence")), "kind": _kind(s, stp), "approvals": stp.get("approvals", 0),
                "represents": _first(s, stp, "represents"), "image": _first(s, stp, "image"),
            }.items() if v is not None}
            for stp in s.steps
        ],
        "quotes": [
            {"text": q["text"], "url": q["url"], **{k: v for k, v in s.lock.get(quote_key(q), {}).items() if k in ("found", "checked_at")}}
            for q in s.quotes if q.get("text") and q.get("url")
        ],
    }


def _first(s: Study, stp: dict, what: str):
    for i in _ids(stp.get("evidence")):
        ev = s.evidence.get(i)
        if ev is None:
            continue
        if what == "represents" and ev.represents:
            return ev.represents
        if what == "image" and ev.image:
            return f"evidence/{ev.image.name}"
    return None


def _evidence_sentence(s: Study) -> str:
    """'The evidence is 17 agent session transcript excerpts and 2 ...' plus the path note."""
    from collections import Counter
    c = Counter(ev.kind for ev in s.evidence.values())
    if not c:
        return ""
    words = {"run": ("live capture", "live captures"), "transcript": ("excerpt from the agent session transcript", "excerpts from the agent session transcript"),
             "screen": ("screen read-out", "screen read-outs"), "formatted": ("tool output reformatted by the test script", "tool outputs reformatted by the test script"),
             "screenshot": ("screenshot", "screenshots"), "note": ("typed note", "typed notes")}
    parts = [f"{n} {words.get(k, (k, k))[n != 1]}" for k, n in c.most_common()]
    text = "The evidence is " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."
    used = set()
    for ev in s.evidence.values():
        m = re.search(r"replaced with (.*)$", ev.meta.get("redacted", ""))
        if m:
            used |= {x.strip() for x in m.group(1).split(",") if x.strip()}
    if used:
        names = sorted(used)
        text += f" Local paths are shown as {names[0] if len(names) == 1 else ', '.join(names[:-1]) + ' and ' + names[-1]}."
    return text


def _kind(s: Study, stp: dict) -> str:
    ev = _ids(stp.get("evidence"))
    kinds = {s.evidence[i].meta.get("kind", "?") for i in ev if i in s.evidence}
    return "/".join(sorted(kinds)) or "?"


def markdown(s: Study) -> str:
    st = s.data.get("study", {})
    subs = s.subjects
    tested_list = ", ".join(f"{x['name']} {x['version']}" for x in subs)
    out = []
    box = (f"> **How this was tested.** On {st.get('date')}, {st.get('tester')} installed and ran {tested_list}"
           + (f" on {st['platform']}" if st.get("platform") else "") + ". "
           "Every terminal line quoted here comes from that session. "
           + (_evidence_sentence(s) + " " if s.evidence else "")
           + "Where something is marked documented, it comes from the project's own docs and was not tested.")
    if st.get("not_tested"):
        box += f" Not tested: {st['not_tested']}"
    out += [box, ""]

    if s.capabilities:
        out.append("| Capability | " + " | ".join(x["name"] for x in subs) + " |")
        out.append("|---|" + "---|" * len(subs))
        for cap in s.capabilities:
            cells = cap.get("cells", {})
            row = [f"**{cap['label']}**" if cap.get("gap") else cap["label"]]
            row += [LABEL.get(cells.get(x["id"], {}).get("status"), "?") for x in subs]
            out.append("| " + " | ".join(row) + " |")
        if any(c.get("gap") for c in s.capabilities):
            out.append("")
            out.append("Rows in bold are gaps: not found for any of them.")
        out.append("")

    verified = [q for q in s.quotes if s.lock.get(quote_key(q), {}).get("found")]
    if verified:
        out.append("<details><summary>Quotes checked against their sources</summary>")
        out.append("")
        for q in verified:
            r = s.lock[quote_key(q)]
            out.append(f"- “{q['text']}”: [{q['url']}]({q['url']}), checked {r['checked_at'][:10]}")
        out += ["", "</details>", ""]

    out.append(f"*Versions tested: {tested_list}, on {st.get('date')}. "
               "These projects change fast, so check their release notes before relying on any limitation described here.*")
    return "\n".join(out) + "\n"


def write(s: Study, out_dir: Path | None = None) -> tuple[Path, Path]:
    out_dir = Path(out_dir or s.root)
    out_dir.mkdir(parents=True, exist_ok=True)
    j = out_dir / "receipts.json"
    m = out_dir / "receipts.md"
    j.write_text(json.dumps(data(s), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    m.write_text(markdown(s), encoding="utf-8")
    return j, m
