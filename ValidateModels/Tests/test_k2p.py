#!/bin/python3

# Tests for Tamura Nei model

import os, sys, numpy as np
sys.path.append("../")
import K2P

def create_dawg():
    f = open('../Data/k2p.dawg','w')
    # remember dawg order is aY,aR,b
    str_out = ['Tree.Tree = "(A:0.3)B;"\n', 'Subst.Model = "K2P"\n', 'Subst.Params = 2.0, 1.0\n',  'Root.Length = 1000000\n', 'Sim.Reps = 3\n']
    f.writelines(str_out)
    f.close()

def run_dawg():
    os.system("make -s -C ../Data/ k2p.1.fasta k2p.2.fasta")

def run_K2P():
    return K2P.EM_K2P(np.power(10.0,-15),K2P.readFreqMatrix("../Data/k2p.1.fasta","../Data/k2p.2.fasta"))

def get_rates(estimates):
    # convert estimates to dawg values
    #   d is the normalization value
    d = 1
    a = (estimates[1]/0.5+estimates[2])*d
    b = estimates[2]*d
    return [a,b]

def check_range(estimate,value):
    # epsilon is 1%
    return (abs(value-estimate)/value < 0.01)

def test_EM_K2P(estimates):
    # create true values array
    #          [t,  a,  b  ]
    t_values = [0.3,2.0,1.0]
    values = ['t','a','b']
    # convert estimates to dawg values
    estimates[1:3] = get_rates(estimates)

    e = 0
    # check parameters
    for i in range(3):
        #assert(check_range(estimates[i],t_values[i]) == True)
        if(not check_range(estimates[i],t_values[i])):
            print('Assertion failed.... ',values[i],': ',estimates[i],' != ',t_values[i])
            e += 1
    return e

def main():
    create_dawg()
    run_dawg()
    est_params = run_K2P()
    if(type(est_params) is not list):
        #log-likelihood error ocurred
        print('Test failed: log-likelihood error')
    else:
        result = test_EM_K2P(est_params)
        if(result == 0):
            print('All tests passed!')
        else:
            print(result,' tests failed.')

if __name__ == '__main__':
    main()
