"""Predetermined finite regression and rejection checks on owned toy models."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
import checker

def model(i): return checker.load(ROOT/'cases'/f'case-{i:03}.json')
def cert(i): return checker.load(ROOT/'results'/'certificates'/f'case-{i:03}.json')

class CheckerTests(unittest.TestCase):
    def reject(self,m,c):
        with self.assertRaises((checker.Invalid,ValueError,OverflowError)):
            checker.verify(m,c)
    def test_all_retained_certificates(self):
        for p in sorted((ROOT/'results'/'certificates').glob('case-*.json')):
            with self.subTest(case=p.stem):
                m=checker.load(ROOT/'cases'/p.name); c=checker.load(p)
                expected=json.loads((ROOT/'results'/p.name).read_text())['exact_status']
                self.assertEqual(checker.verify(m,c),expected)
    def test_every_certificate_rejects_wrong_length(self):
        for p in sorted((ROOT/'results'/'certificates').glob('case-*.json')):
            with self.subTest(case=p.stem):
                m=checker.load(ROOT/'cases'/p.name); c=checker.load(p)
                field='cover' if c['kind']=='finite_cover' else 'multipliers'
                c[field].append(0); self.reject(m,c)
    def test_no_unknown_proof_kind(self):
        c=cert(1);c['kind']='unchecked';self.reject(model(1),c)
    def test_no_extra_certificate_field(self):
        c=cert(1);c['decision']='PROVED';self.reject(model(1),c)
    def test_no_missing_witness(self):
        c=cert(1);del c['witness'];self.reject(model(1),c)
    def test_infeasible_witness(self):
        c=cert(1);c['witness']=[0,0];self.reject(model(1),c)
    def test_fractional_witness(self):
        c=cert(1);c['witness']=['1/2',0];self.reject(model(1),c)
    def test_boolean_witness(self):
        c=cert(1);c['witness']=[True,0];self.reject(model(1),c)
    def test_negative_multiplier(self):
        c=cert(1);j=next(j for j,v in enumerate(c['multipliers']) if Fraction(v)>0)
        c['multipliers'][j]=str(-Fraction(c['multipliers'][j]));self.reject(model(1),c)
    def test_zero_wrong_identity(self):
        c=cert(1);c['multipliers']=[0]*len(c['multipliers']);self.reject(model(1),c)
    def test_float_multiplier(self):
        c=cert(1);c['multipliers'][0]=0.0;self.reject(model(1),c)
    def test_no_rounding_as_linear(self):
        c=cert(2);c['kind']='linear';self.reject(model(2),c)
    def test_strict_quantum_boundary(self):
        self.reject(model(4),cert(2))
    def test_widened_interval_invalidates_proof(self):
        self.reject(model(5),cert(2))
    def test_fine_precision_is_not_float(self):
        for i in (51,53,55): self.assertEqual(checker.verify(model(i),cert(i)),'PROVED')
        for i in (52,54,56): self.reject(model(i),cert(i-1))
    def test_forged_inconsistency_zero(self):
        c=cert(41);c['multipliers']=[0]*len(c['multipliers']);self.reject(model(41),c)
    def test_inconsistency_cannot_carry_witness(self):
        c=cert(41);c['witness']=[0,0];self.reject(model(41),c)
    def test_inconsistency_wrong_model(self):
        self.reject(model(1),cert(41))
    def test_finite_cover_missing_entry(self):
        c=cert(45);c['cover'].pop();self.reject(model(45),c)
    def test_finite_cover_false_property(self):
        c=cert(45);c['cover']=[-1]*len(c['cover']);self.reject(model(45),c)
    def test_finite_cover_false_row(self):
        c=cert(45);c['cover']=[0]*len(c['cover']);self.reject(model(45),c)
    def test_finite_cover_unknown_row(self):
        c=cert(45);c['cover'][0]=128;self.reject(model(45),c)
    def test_finite_cover_boolean_tag(self):
        c=cert(45);c['cover'][0]=True;self.reject(model(45),c)
    def test_inconsistent_cover_has_no_property_tags(self):
        c=cert(48);c['cover']=[-1]*len(c['cover']);self.reject(model(48),c)
    def test_inconsistent_cover_no_witness(self):
        c=cert(48);c['witness']=[0];self.reject(model(48),c)
    def test_model_property_changed(self):
        m=model(1);m['assertion']['upper']='-1';self.reject(m,cert(1))
    def test_weaker_property_remains_valid(self):
        m=model(1);m['assertion']['upper']='1';self.assertEqual(checker.verify(m,cert(1)),'PROVED')
    def test_affine_quantum(self):
        self.assertEqual(checker.verify(model(85),cert(85)),'PROVED')
        self.assertEqual(checker.quantum([Fraction(2,3)],Fraction(1,3)),Fraction(1,3))
    def test_no_forward_edge(self):
        m=model(1);m['nodes'][2]['terms'][0][0]=2;self.reject(m,cert(1))
    def test_no_duplicate_parent(self):
        m=model(1);m['nodes'][2]['terms'].append(m['nodes'][2]['terms'][0]);self.reject(m,cert(1))
    def test_canonical_input_order(self):
        m=model(1);m['nodes'][0]['input']=1;self.reject(m,cert(1))
    def test_state_budget(self):
        m=model(1);m['domain']['bounds']=[[0,100],[0,100]];self.reject(m,cert(1))
    def test_node_budget(self):
        m=model(1);m['nodes'] += [{'constant':0,'terms':[]}]*63;self.reject(m,cert(1))
    def test_observation_budget(self):
        m=model(1);m['observations']*=9;self.reject(m,cert(1))
    def test_inequality_budget(self):
        m=model(1);m['assumptions']=copy.deepcopy(m['observations']*32);self.reject(m,cert(1))
    def test_malformed_empty_grid(self):
        m=model(1);m['domain']['bounds'][0]=[2,1];self.reject(m,cert(1))
    def test_input_bit_budget(self):
        m=model(1);m['nodes'][2]['constant']=str(2**513);self.reject(m,cert(1))
    def test_malformed_rationals(self):
        for value in ['1/0','1/-2','--1','+1','1.5','NaN','Infinity','1/2/3',True,0.5,None]:
            with self.subTest(value=value),self.assertRaises((ValueError,OverflowError)):
                checker.rational(value)
    def test_duplicate_keys_float_and_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'input.json'
            for text in ['{"x":1,"x":2}','{"x":0.1}','{"x":NaN}']:
                p.write_text(text)
                with self.assertRaises(checker.Invalid):checker.load(p)
    def test_missing_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(checker.Invalid):checker.load(Path(d)/'absent.json')
    def test_directed_graph_compilation_agrees(self):
        # Independently evaluate forms at one fixed point; no producer imports.
        m=model(85);bounds,A,b,c,q0=checker.compile_model(m)
        self.assertEqual(c,[Fraction(2,3)]);self.assertEqual(q0,0)
    def test_reversed_interval_inconsistency(self):
        self.assertEqual(checker.verify(model(86),cert(86)),'INCONSISTENT')

    def test_valid_admission_limits(self):
        # Degenerate one-state input, not a scalability benchmark for the LP producer.
        m={'id':'admission-limits','family':'validation-only',
           'domain':{'kind':'integer_grid','bounds':[[0,0] for _ in range(16)]},
           'nodes':[{'input':i} for i in range(16)],'assumptions':[],
           'observations':[],'assertion':{'node':63,'upper':0}}
        m['nodes'].append({'constant':0,'terms':[[i,1] for i in range(16)]})
        for i in range(17,64):m['nodes'].append({'constant':0,'terms':[[i-1,1]]})
        m['observations']=[{'node':i,'lower':0,'upper':0} for i in range(16)]
        m['assumptions']=[{'node':0,'lower':0,'upper':0} for _ in range(32)]
        lam=[int(i%2==1) for i in range(32)]+[0]*96
        self.assertEqual(checker.verify(m,{'kind':'linear','witness':[0]*16,'multipliers':lam}),'PROVED')
    def test_cover_at_state_ceiling(self):
        m=model(57)
        c={'kind':'finite_cover','decision':'PROVED','witness':[0,0,0],
           'cover':[-1 if i%16==0 else 7 for i in range(4096)]}
        self.assertEqual(checker.verify(m,c),'PROVED')
    def test_unused_expression_growth_is_bounded(self):
        m=model(83)
        m['nodes'].append({'constant':str(2**511),'terms':[]})
        for _ in range(8):m['nodes'].append({'constant':0,'terms':[[len(m['nodes'])-1,str(2**511)]]})
        self.reject(m,cert(83))

if __name__=='__main__':unittest.main(verbosity=2)
