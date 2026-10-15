"""Non-enumerative audit metadata and bibliography-guard regressions."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "audit_reviewer_gate", ROOT / "reviewer_hardening/reviewer_gate.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class AuditMetadataTests(unittest.TestCase):
    def run_static(self, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            here = root / "reviewer_hardening"
            here.mkdir()
            script = here / "static_code_audit.py"
            shutil.copyfile(ROOT / "reviewer_hardening/static_code_audit.py", script)
            (root / "sample.py").write_text(source, encoding="utf-8")
            run = subprocess.run([sys.executable, "-B", str(script)],
                                 capture_output=True, text=True, timeout=10)
            output = here / "static_code_audit.json"
            return run, json.loads(output.read_text()) if output.exists() else None

    def test_static_metadata_reports_source_and_imports(self):
        run, data = self.run_static("import json\nvalue = 3\n")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(data["status"], "PASS")
        self.assertEqual(data["python_files"], 2)
        row = next(row for row in data["files"] if row["path"] == "sample.py")
        self.assertEqual(set(row), {"path", "bytes", "imports"})
        self.assertEqual(row["imports"], ["json"])
        self.assertGreater(row["bytes"], 0)
        self.assertEqual(data["forbidden_constructs"], [])

    def test_static_guards_still_reject_dynamic_execution_and_shell(self):
        for source in ("eval('1')\n", "import subprocess\nsubprocess.run([], shell=True)\n"):
            with self.subTest(source=source):
                run, data = self.run_static(source)
                self.assertNotEqual(run.returncode, 0)
                self.assertIsNone(data)

    def test_gate_consumes_structural_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            here = Path(directory)
            (here / "static_code_audit.json").write_text(json.dumps({
                "status": "PASS", "forbidden_constructs": [],
                "python_files": 2, "total_bytes": 32}))
            with patch.object(GATE, "HERE", here):
                self.assertEqual(GATE.check_static_code(),
                                 {"python_files": 2, "total_bytes": 32})

    def test_gate_rejects_failed_or_forbidden_static_report(self):
        with tempfile.TemporaryDirectory() as directory:
            here = Path(directory)
            for status, forbidden in (("FAIL", []), ("PASS", ["sample: eval"])):
                (here / "static_code_audit.json").write_text(json.dumps({
                    "status": status, "forbidden_constructs": forbidden,
                    "python_files": 2, "total_bytes": 32}))
                with patch.object(GATE, "HERE", here):
                    with self.assertRaises(AssertionError):
                        GATE.check_static_code()

    def test_bibliography_guard_preserves_count_and_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            paper = project / "paper"
            paper.mkdir()
            good = {"status": "PASS", "bib_entries": 70, "unique_cited_keys": 70,
                    "missing_entries": [], "unused_entries": []}
            path = paper / "reference-audit.json"
            path.write_text(json.dumps(good))
            with patch.object(GATE, "PROJECT", project):
                self.assertEqual(GATE.check_bibliography_audit()["entries"], 70)
                for field, value in (("status", "FAIL"), ("bib_entries", 69),
                                     ("unique_cited_keys", 69),
                                     ("missing_entries", ["missing"]),
                                     ("unused_entries", ["unused"])):
                    with self.subTest(field=field):
                        path.write_text(json.dumps(dict(good, **{field: value})))
                        with self.assertRaises(AssertionError):
                            GATE.check_bibliography_audit()


if __name__ == "__main__":
    unittest.main()
