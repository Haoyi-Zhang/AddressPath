"""Independent finite oracle: evaluate the DAG directly at each input state.

Does not import the producer, checker, graph linearizer, or certificate logic.
Only aggregate counts and maxima, never violating states, are returned.
"""
from fractions import Fraction
from itertools import product

def evaluate(model):
    total=0;feasible=0;max_q=None
    for inputs in product(*(range(lo,hi+1) for lo,hi in model['domain']['bounds'])):
        total+=1;values=[]
        for node in model['nodes']:
            if 'input' in node: value=Fraction(inputs[node['input']])
            else:
                value=Fraction(node['constant'])
                for parent,weight in node['terms']:
                    value+=Fraction(weight)*values[parent]
            values.append(value)
        ok=True
        for interval in model['assumptions']+model['observations']:
            val=values[interval['node']]
            if val<Fraction(interval['lower']) or val>Fraction(interval['upper']):
                ok=False;break
        if not ok: continue
        feasible+=1
        q=values[model['assertion']['node']]-Fraction(model['assertion']['upper'])
        if max_q is None or q>max_q: max_q=q
    status='INCONSISTENT' if not feasible else 'PROVED' if max_q<=0 else 'INSUFFICIENT'
    return {'status':status,'states':total,'feasible_states':feasible,
            'max_q':None if max_q is None else str(max_q)}
