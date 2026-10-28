"""Evidence files: what actually happened, kept word for word.

Each piece of evidence is one file in <study>/evidence/, named NNN-slug.log:
a short header, then the output exactly as it appeared. Screenshots are kept
next to their header file as NNN-slug.png (or .jpg/.webp/.gif).

Every file says what kind of record it is, and what it shows:

  kind        how the record was made
  represents  one sentence a reader can trust: what this evidence shows

Kinds:
  run         receipts ran the command and captured stdout and stderr live
  transcript  copied from an agent session's transcript (e.g. a Claude Code log)
  screen      text read off a screen: a TUI, a dialog, a status line
  formatted   a tool's real output, reformatted by your script (e.g. JSON to a table)
  screenshot  an image of a screen; the header carries the description
  note        anything else you typed or pasted in

Local paths are replaced before anything is written, so evidence can be
published without your home folder in it. The header records that a
replacement happened and what was put in its place, never the original.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HEADER_END = "# ---"
KINDS = ("run", "transcript", "screen", "formatted", "screenshot", "note")
KIND_LABEL = {
    "run": "captured live",
    "transcript": "agent session transcript",
    "screen": "read off the screen",
    "formatted": "tool output, reformatted by the test script",
    "screenshot": "screenshot",
    "note": "typed or pasted in",
}
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")
_NAME = re.compile(r"^(\d{3})-([a-z0-9][a-z0-9-]*)\.log$")


@dataclass
class Evidence:
    id: str
    name: str
    path: Path
    meta: dict
    body: str
    image: Path | None = field(default=None)

    @property
    def kind(self) -> str:
        return self.meta.get("kind", "note")

    @property
    def represents(self) -> str:
        return self.meta.get("represents", "")


# ------------------------------------------------------------------ redaction

def default_redactions() -> dict[str, str]:
    """Without a [redact] table, the home folder becomes '~'."""
    home = os.path.expanduser("~")
    return {home: "~"} if home and home != "/" else {}


def redact(text: str, table: dict[str, str], used: set | None = None) -> tuple[str, int]:
    """Replace each local path with its stand-in, longest first. Returns the new
    text and how many replacements were made; records the stand-ins used in `used`."""
    n = 0
    for real in sorted(table, key=len, reverse=True):
        if real and real in text:
            n += text.count(real)
            text = text.replace(real, table[real])
            if used is not None:
                used.add(table[real])
    return text, n


def _redaction_note(used: set, n: int) -> str:
    return f"{n} local path(s) replaced with {', '.join(sorted(used))}"


# ------------------------------------------------------------------ reading

def _slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:48] or "evidence"


def evidence_dir(study: Path) -> Path:
    d = study / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse(text: str) -> tuple[dict, str]:
    meta, body = {}, text
    marker = HEADER_END + "\n"
    if marker in text:
        head, body = text.split(marker, 1)
        for line in head.splitlines():
            if line.startswith("# ") and ": " in line:
                k, v = line[2:].split(": ", 1)
                meta[k.strip()] = v.strip()
    return meta, body


def render(eid: str, meta: dict, body: str) -> str:
    head = [f"# receipts evidence {eid}"] + [f"# {k}: {v}" for k, v in meta.items() if v not in (None, "")] + [HEADER_END]
    return "\n".join(head) + "\n" + body


def load_all(study: Path) -> dict[str, Evidence]:
    out: dict[str, Evidence] = {}
    d = study / "evidence"
    if not d.is_dir():
        return out
    for p in sorted(d.iterdir()):
        m = _NAME.match(p.name)
        if not m:
            continue
        meta, body = parse(p.read_text(encoding="utf-8", errors="replace"))
        img = next((p.with_suffix(e) for e in IMAGE_EXT if p.with_suffix(e).is_file()), None)
        out[m.group(1)] = Evidence(m.group(1), m.group(2), p, meta, body, img)
    return out


def _next_id(study: Path) -> str:
    ids = [int(k) for k in load_all(study)]
    return f"{(max(ids) + 1) if ids else 1:03d}"


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ------------------------------------------------------------------ writing

def _write(study: Path, name: str, meta: dict, body: str, table: dict[str, str], image: Path | None = None) -> Evidence:
    eid = _next_id(study)
    path = evidence_dir(study) / f"{eid}-{_slug(name)}.log"
    n, used = 0, set()
    clean_meta = {}
    for k, v in meta.items():
        v, c = redact(str(v), table, used) if v is not None else (v, 0)
        clean_meta[k] = v
        n += c
    body, c = redact(body, table, used)
    n += c
    if n:
        clean_meta["redacted"] = _redaction_note(used, n)
    img = None
    if image is not None:
        img = path.with_suffix(image.suffix.lower())
        shutil.copyfile(image, img)
        clean_meta["image"] = img.name
    path.write_text(render(eid, clean_meta, body), encoding="utf-8")
    return Evidence(eid, _slug(name), path, clean_meta, body, img)


def run(study: Path, name: str, argv: list[str], represents: str = "", cwd: str | None = None,
        echo: bool = True, table: dict[str, str] | None = None) -> tuple[Evidence, int]:
    """Run a command, show its output live, and save it word for word."""
    started = _now()
    proc = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, text=True, errors="replace", bufsize=1)
    chunks: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        chunks.append(line)
        if echo:
            sys.stdout.write(line)
            sys.stdout.flush()
    proc.stdout.close()
    code = proc.wait()
    meta = {"kind": "run", "represents": represents, "name": name, "at": started,
            "cwd": os.path.abspath(cwd or os.getcwd()), "cmd": shlex.join(argv), "exit": str(code)}
    t = default_redactions() if table is None else table
    return _write(study, name, meta, "".join(chunks), t), code


def note(study: Path, name: str, body: str, kind: str = "note", represents: str = "", source: str = "",
         image: Path | None = None, table: dict[str, str] | None = None) -> Evidence:
    """Keep evidence captured some other way, labeled with what kind of record it is."""
    if kind not in KINDS or kind == "run":
        raise ValueError(f"kind must be one of {', '.join(k for k in KINDS if k != 'run')} (only `receipts run` makes 'run')")
    if kind == "screenshot" and image is None:
        raise ValueError("a screenshot needs --file")
    meta = {"kind": kind, "represents": represents, "name": name, "at": _now(), "source": source}
    t = default_redactions() if table is None else table
    return _write(study, name, meta, body if (not body or body.endswith("\n")) else body + "\n", t, image)


def relabel(ev: Evidence, kind: str | None = None, represents: str | None = None,
            table: dict[str, str] | None = None) -> Evidence:
    """Update an existing evidence file in place: set its kind or description, and
    replace any local paths left in it. The output itself is not otherwise touched."""
    meta = dict(ev.meta)
    if kind:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {', '.join(KINDS)}")
        if kind == "run" and meta.get("kind") != "run":
            raise ValueError("only `receipts run` can make evidence of kind 'run'")
        meta["kind"] = kind
    if represents is not None:
        meta["represents"] = represents
    body, n, used = ev.body, 0, set()
    if table:
        for k in list(meta):
            if k == "redacted":
                continue
            meta[k], c = redact(meta[k], table, used)
            n += c
        body, c = redact(body, table, used)
        n += c
    if n:
        prev = re.match(r"(\d+) local path\(s\) replaced with (.*)$", meta.get("redacted", ""))
        if prev:
            used |= {x.strip() for x in prev.group(2).split(",")}
        meta["redacted"] = _redaction_note(used, n + (int(prev.group(1)) if prev else 0))
    # keep a stable key order: kind and represents first
    ordered = {k: meta[k] for k in ("kind", "represents") if k in meta}
    ordered.update({k: v for k, v in meta.items() if k not in ordered})
    ev.path.write_text(render(ev.id, ordered, body), encoding="utf-8")
    return Evidence(ev.id, ev.name, ev.path, ordered, body, ev.image)


def find_local_paths(text: str) -> list[str]:
    """Real home-folder paths still present in a piece of evidence."""
    home = os.path.expanduser("~")
    pats = [re.escape(home)] if home and home != "/" else []
    pats += [r"/Users/[A-Za-z0-9._-]+", r"/home/[A-Za-z0-9._-]+", r"/private/var/folders/\S+", r"C:\\Users\\[^\\\s]+"]
    found = set()
    for p in pats:
        found.update(re.findall(p, text))
    return sorted(found)
