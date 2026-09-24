#!/usr/bin/env python3
from __future__ import annotations
import copy, importlib.util, json, tempfile, unittest
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('vac',HERE/'verify_architecture_cases.py')
vac=importlib.util.module_from_spec(SPEC); assert SPEC.loader; SPEC.loader.exec_module(vac)
BASE=json.loads((HERE/'architecture_cases.json').read_text())

def case(cid): return copy.deepcopy(next(c for c in BASE['cases'] if c['id']==cid))

class ArchitectureCaseTests(unittest.TestCase):
    def test_valid_suite(self):
        for c in BASE['cases']:
            vac.validate_case(c)
            decision,_,_=vac.ground_truth(c)
            self.assertEqual(decision,c['expected']['ground_truth'])
            self.assertEqual(vac.check_compact_certificate(c),c['expected']['compact_method'])
    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.json'; p.write_text('{"schema":"a","schema":"b"}')
            with self.assertRaises(ValueError): vac.load_strict(p)
    def test_float_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'x.json'; p.write_text('{"x":1.5}')
            with self.assertRaises(ValueError): vac.load_strict(p)
    def test_unknown_case_field(self):
        c=case('sv39_serial_permission_gate'); c['surprise']=1
        with self.assertRaises(ValueError): vac.validate_case(c)
    def test_cycle_rejected_during_path_reconstruction(self):
        c=case('negative_control_unconstrained_bypass')
        c['edges'].append({'id':'back','src':'walk','dst':'request','open_var':'walk'})
        vac.validate_case(c)
        with self.assertRaises(ValueError): vac.canonical_paths(c)
    def test_nonbinary_edge_variable_rejected(self):
        c=case('negative_control_unconstrained_bypass'); c['variables']['walk']=[0,2]
        with self.assertRaises(ValueError): vac.validate_case(c)
    def test_missing_path_rejected(self):
        c=case('riscv_two_stage_correlated_acceptance'); c['certificate']['paths'].pop()
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_duplicate_path_rejected(self):
        c=case('riscv_two_stage_correlated_acceptance'); c['certificate']['paths'].append(copy.deepcopy(c['certificate']['paths'][0]))
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_noncanonical_path_rejected(self):
        c=case('riscv_two_stage_correlated_acceptance'); c['certificate']['paths'][0]['edge_ids'].reverse()
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_wrong_multiplier_rejected(self):
        c=case('riscv_two_stage_correlated_acceptance'); c['certificate']['paths'][0]['multipliers']['ub:commit_a']='1'
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_negative_multiplier_rejected(self):
        c=case('riscv_two_stage_correlated_acceptance'); c['certificate']['paths'][0]['multipliers']['ub:commit_a']='-2'
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_unknown_witness_row_rejected(self):
        c=case('sv39_serial_permission_gate'); c['certificate']['cut_edges'][0]['multipliers']={'constraint:nope':'1'}
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_cut_that_misses_path_rejected(self):
        c=case('sv39_serial_permission_gate'); c['certificate']['cut_edges']=[]
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_unconstrained_bypass_is_unsafe(self):
        c=case('negative_control_unconstrained_bypass')
        decision,allowed,bad=vac.ground_truth(c)
        self.assertEqual(decision,'INSUFFICIENT'); self.assertGreater(bad,0); self.assertGreater(allowed,bad-1)
    def test_forged_none_with_extra_fields_rejected(self):
        c=case('negative_control_unconstrained_bypass'); c['certificate']['fake']=1
        with self.assertRaises(ValueError): vac.check_compact_certificate(c)
    def test_expectation_drift_detected(self):
        c=case('negative_control_unconstrained_bypass')
        decision,_,_=vac.ground_truth(c)
        self.assertNotEqual(decision,'PROVED')

if __name__=='__main__': unittest.main(verbosity=2)
