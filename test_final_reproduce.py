#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('final_reproduce',HERE/'final_reproduce.py')
mod=importlib.util.module_from_spec(SPEC); assert SPEC.loader; SPEC.loader.exec_module(mod)


class FinalReproducePathTests(unittest.TestCase):
    def test_safe_repository_subdirectory(self):
        candidate=mod.validate_output_path(HERE/'safe-output-for-test')
        self.assertEqual(candidate, (HERE/'safe-output-for-test').resolve())

    def test_repository_root_rejected(self):
        with self.assertRaises(SystemExit): mod.validate_output_path(HERE)

    def test_repository_ancestor_rejected(self):
        with self.assertRaises(SystemExit): mod.validate_output_path(HERE.parent)

    def test_external_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(SystemExit): mod.validate_output_path(Path(td)/'outside')

    def test_symlink_escape_rejected_without_touching_sentinel(self):
        with tempfile.TemporaryDirectory() as external:
            sentinel=Path(external)/'sentinel.txt'; sentinel.write_text('keep')
            with tempfile.TemporaryDirectory(dir=HERE) as local:
                link=Path(local)/'escape'; link.symlink_to(Path(external),target_is_directory=True)
                with self.assertRaises(SystemExit): mod.validate_output_path(link/'output')
                self.assertEqual(sentinel.read_text(),'keep')


if __name__=='__main__': unittest.main(verbosity=2)
