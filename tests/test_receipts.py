import json
import sys
import tempfile
import unittest
from pathlib import Path

from receipts import build, evidence, ledger, quotes
from receipts.cli import main
from receipts.text import contains, normalize

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "agent-fleet"

BASE = """
[study]
title = "T"
date = "2026-10-27"
tester = "me"

[[subject]]
id = "a"
name = "A"
version = "1.0"
"""


def study(extra: str = "", notes: dict | None = None) -> Path:
    d = Path(tempfile.mkdtemp())
    (d / "ledger.toml").write_text(BASE + extra, encoding="utf-8")
    for name, body in (notes or {}).items():
        evidence.note(d, name, body)
    return d


def errors(d: Path) -> list[str]:
    return [p.message for p in ledger.validate(ledger.load(d)) if p.level == "error"]


class TextTests(unittest.TestCase):
    def test_folds_quotes_dashes_space_and_case(self):
        self.assertEqual(normalize("Herdr doesn’t  wrap THEM — ok"), "herdr doesn't wrap them - ok")

    def test_strips_terminal_colors(self):
        self.assertTrue(contains("\x1b[32mPASS\x1b[0m test_basic", "PASS test_basic"))

    def test_empty_needle_never_matches(self):
        self.assertFalse(contains("anything", "   "))


class LedgerTests(unittest.TestCase):
    def test_tested_needs_evidence(self):
        d = study('[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "tested", note = "n" }\n')
        self.assertTrue(any("tested without evidence" in e for e in errors(d)))

    def test_cited_evidence_must_exist(self):
        d = study('[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "tested", note = "n", evidence = ["007"] }\n')
        self.assertTrue(any("evidence 007 does not exist" in e for e in errors(d)))

    def test_excerpt_must_be_word_for_word(self):
        cap = '[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "tested", note = "n", evidence = ["001"], excerpt = "%s" }\n'
        ok = study(cap % "all three tests pass", {"run": "All three  tests pass.\n"})
        self.assertEqual(errors(ok), [])
        bad = study(cap % "all tests pass", {"run": "All three tests pass.\n"})
        self.assertTrue(any("excerpt not found" in e for e in errors(bad)))

    def test_documented_needs_source(self):
        d = study('[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "documented", note = "n" }\n')
        self.assertTrue(any("without a source" in e for e in errors(d)))

    def test_gap_row_must_be_all_not_found(self):
        d = study('[[capability]]\nid="x"\nlabel="X"\ngap = true\n[capability.cells]\na = { status = "documented", note = "n", source = "u" }\n')
        self.assertTrue(any("marked as a gap" in e for e in errors(d)))

    def test_every_subject_needs_a_cell(self):
        d = study('[[subject]]\nid="b"\nname="B"\nversion="2"\n[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "not-found", note = "n" }\n')
        self.assertTrue(any("no cell" in e for e in errors(d)))

    def test_subject_needs_version(self):
        d = Path(tempfile.mkdtemp())
        (d / "ledger.toml").write_text('[study]\ntitle="T"\ndate="d"\ntester="t"\n[[subject]]\nid="a"\nname="A"\n', encoding="utf-8")
        self.assertTrue(any("missing version" in e for e in errors(d)))

    def test_unknown_status_rejected(self):
        d = study('[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "probably", note = "n" }\n')
        self.assertTrue(any("status must be one of" in e for e in errors(d)))

    def test_step_excerpt_checked(self):
        d = study('[[step]]\ntitle="S"\nevidence=["001"]\nexcerpt="Kernel ready."\n', {"start": "Starting daemon...\nKernel ready.\n"})
        self.assertEqual(errors(d), [])


class QuoteTests(unittest.TestCase):
    def test_found_missing_and_blocked(self):
        d = study('[[quote]]\ntext="where your coding agents live"\nurl="https://a.test/"\n'
                  '[[quote]]\ntext="the fastest runtime ever"\nurl="https://a.test/"\n'
                  '[[quote]]\ntext="anything"\nurl="https://b.test/"\n')
        pages = {
            "https://a.test/": "<html><title>A</title><script>var x='fastest runtime ever'</script><p>Herdr is where your <b>coding agents</b> live.</p></html>",
            "https://b.test/": "<html><head><title>Just a moment...</title></head><body>checking</body></html>",
        }
        s = ledger.load(d)
        res = quotes.check(s, fetcher=lambda u: pages[u])
        self.assertEqual([r["found"] for r in res], [True, False, False])
        self.assertIn("blocked", res[2]["error"])
        # script text must not count as page text
        self.assertNotIn("context", {k for k, v in res[1].items() if v})
        # the lock file makes `check` report the miss as an error
        self.assertTrue(any("not found at" in e for e in errors(d)))

    def test_unverified_quote_is_a_warning(self):
        d = study('[[quote]]\ntext="t"\nurl="https://a.test/"\n')
        probs = ledger.validate(ledger.load(d))
        self.assertEqual([p.level for p in probs], ["warning"])


class EvidenceTests(unittest.TestCase):
    def test_run_captures_output_and_exit_code(self):
        d = Path(tempfile.mkdtemp())
        ev, code = evidence.run(d, "Python says hi", [sys.executable, "-c", "import sys; print('hi'); sys.exit(3)"], echo=False)
        self.assertEqual((ev.id, ev.name, code), ("001", "python-says-hi", 3))
        again = evidence.load_all(d)["001"]
        self.assertEqual(again.body, "hi\n")
        self.assertEqual(again.meta["exit"], "3")
        self.assertEqual(again.meta["kind"], "run")

    def test_ids_increment(self):
        d = Path(tempfile.mkdtemp())
        evidence.note(d, "one", "a")
        self.assertEqual(evidence.note(d, "two", "b").id, "002")


class LabelTests(unittest.TestCase):
    def test_note_kinds_and_represents(self):
        d = Path(tempfile.mkdtemp())
        ev = evidence.note(d, "queue", "x\n", kind="transcript", represents="The queue after the handoff")
        again = evidence.load_all(d)[ev.id]
        self.assertEqual((again.kind, again.represents), ("transcript", "The queue after the handoff"))

    def test_note_cannot_claim_run(self):
        with self.assertRaises(ValueError):
            evidence.note(Path(tempfile.mkdtemp()), "x", "y", kind="run")

    def test_screenshot_needs_image_and_keeps_it(self):
        d = Path(tempfile.mkdtemp())
        with self.assertRaises(ValueError):
            evidence.note(d, "s", "desc", kind="screenshot")
        png = d / "in.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        ev = evidence.note(d, "Orca window", "The Orca window", kind="screenshot", represents="The Orca window", image=png)
        again = evidence.load_all(d)[ev.id]
        self.assertEqual(again.image.name, "001-orca-window.png")
        self.assertEqual(again.meta["image"], "001-orca-window.png")

    def test_missing_represents_is_a_warning(self):
        d = study(notes={"a": "b"})
        probs = ledger.validate(ledger.load(d))
        self.assertTrue(any(p.level == "warning" and "represents" in p.message for p in probs))

    def test_relabel_cannot_promote_to_run(self):
        d = Path(tempfile.mkdtemp())
        ev = evidence.note(d, "a", "b")
        with self.assertRaises(ValueError):
            evidence.relabel(ev, kind="run")


class RedactTests(unittest.TestCase):
    TABLE = {"/Users/alex/Projects": "~/ry-ops/projects", "/Users/alex": "~/ry-ops"}

    def test_longest_path_wins_and_header_says_so(self):
        d = Path(tempfile.mkdtemp())
        ev = evidence.note(d, "p", "/Users/alex/Projects/lab/x and /Users/alex/.config\n", kind="transcript", table=self.TABLE)
        self.assertEqual(ev.body, "~/ry-ops/projects/lab/x and ~/ry-ops/.config\n")
        self.assertEqual(ev.meta["redacted"], "2 local path(s) replaced with ~/ry-ops, ~/ry-ops/projects")

    def test_header_lists_only_stand_ins_used(self):
        ev = evidence.note(Path(tempfile.mkdtemp()), "p", "/Users/alex/.config\n", table=self.TABLE)
        self.assertEqual(ev.meta["redacted"], "1 local path(s) replaced with ~/ry-ops")

    def test_run_redacts_cwd_and_output(self):
        d = Path(tempfile.mkdtemp())
        real = str(d)
        ev, _ = evidence.run(d, "pwd", [sys.executable, "-c", "import os; print(os.getcwd())"], cwd=real, echo=False, table={real: "~/ry-ops/lab"})
        self.assertNotIn(real, ev.path.read_text())
        self.assertIn("~/ry-ops/lab", ev.body)

    def test_check_refuses_real_paths(self):
        d = study(notes={"leak": "see /Users/alex/secret-project\n"})
        self.assertTrue(any("real local path" in e for e in errors(d)))

    def test_ledger_table_expands_tilde(self):
        d = study('[redact]\n"~/Projects" = "~/ry-ops/projects"\n"~" = "~/ry-ops"\n')
        table = ledger.redactions(ledger.load(d))
        import os
        self.assertEqual(table[os.path.expanduser("~/Projects")], "~/ry-ops/projects")
        self.assertEqual(table[os.path.expanduser("~")], "~/ry-ops")


class ExampleTests(unittest.TestCase):
    """The agent-fleet study ships in the repo and must always pass."""

    def test_example_has_no_errors_or_warnings(self):
        self.assertEqual([str(p) for p in ledger.validate(ledger.load(EXAMPLE))], [])

    def test_build_outputs(self):
        out = Path(tempfile.mkdtemp())
        j, m = build.write(ledger.load(EXAMPLE), out)
        data = json.loads(j.read_text())
        self.assertEqual([s["name"] for s in data["subjects"]], ["Orca", "OpenRig", "Herdr"])
        gaps = [c for c in data["capabilities"] if c["gap"]]
        self.assertEqual(len(gaps), 4)
        self.assertTrue(all(cell["status"] == "not-found" for c in gaps for cell in c["cells"].values()))
        self.assertEqual(data["evidence"]["010"]["kind"], "formatted")
        self.assertTrue(all(e.get("represents") for e in data["evidence"].values()))
        self.assertTrue(all("represents" in s for s in data["steps"]))
        md = m.read_text()
        self.assertIn("Local paths are shown as ~/ry-ops", md)
        self.assertIn("How this was tested", md)
        self.assertIn("| **Memory shared across tools and machines** | Not found | Not found | Not found |", md)


class CliTests(unittest.TestCase):
    def test_new_check_build(self):
        d = Path(tempfile.mkdtemp()) / "s"
        self.assertEqual(main(["new", str(d), "--title", "X"]), 0)
        self.assertEqual(main(["new", str(d), "--title", "X"]), 1)  # never overwrites
        self.assertEqual(main(["check", str(d)]), 0)
        self.assertEqual(main(["build", str(d)]), 0)
        self.assertTrue((d / "receipts.json").is_file())

    def test_build_refuses_on_errors(self):
        d = study('[[capability]]\nid="x"\nlabel="X"\n[capability.cells]\na = { status = "tested", note = "n" }\n')
        self.assertEqual(main(["build", str(d)]), 1)
        self.assertEqual(main(["build", str(d), "--force"]), 0)


if __name__ == "__main__":
    unittest.main()
