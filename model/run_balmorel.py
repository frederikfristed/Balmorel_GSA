import os
import sys
import argparse
import multiprocessing as mp
from datetime import timedelta
import time 
from copy import copy
from create_samples import sampler
import pandas as pd

sys.path.append(os.path.abspath("../GSA_parameters/"))
from parameters import GSA_parameters

def get_arg():
    parser = argparse.ArgumentParser(description="Process some arguments.")
    parser.add_argument('--nb_scen', default=1, type=int, help='Number of scenarios (integer)')
    parser.add_argument('--input_sample', default="input_params.csv", type=str, help='Name of the input sampling csv file (str)')
    parser.add_argument('--nb_cores', default=2, type=int, help='Number of cores (integer)')
    parser.add_argument('--path', default='scenario_data', type=str, help='Path to save scenario data')
    parser.add_argument('--sampler', default='Sobol', type=str, help='Sampling strategy used for sampling (Morris, Sobol, LHC, FAST)')
    args = parser.parse_args()
    return args.nb_scen, args.input_sample, args.nb_cores, args.path, args.sampler

def run_scenario(index, sample, parameters, rpath):
    print("Running scenario {}".format(index+1))
    os.system("gams ./Balmorel_finish.gms --id=scenario_{0} --rpath={1} r=s1 threads=1 > ../{1}/log_files/output_file_scenario_{0}.txt".format(index+1, rpath))

if __name__ == '__main__': 
    num_scen, input_file, nb_cores, rpath, sampling_strategy = get_arg()
    if not os.path.isdir("../{}".format(rpath)):
        os.makedirs("../{}".format(rpath))
        os.makedirs("../{}/log_files".format(rpath))
        os.makedirs("../{}/input_data".format(rpath))
        os.makedirs("../{}/output_data".format(rpath))
    
    # Copy input csv file to scenario data input data folder (more easy for gams part)
    os.system("cp ../GSA_parameters/{} ../{}/input_data/input.csv".format(input_file, rpath))
    
    # Sampling
    sampler = sampler(sampling_strategy, input="../{}/input_data/input.csv".format(rpath), N=num_scen, rng=42)
    sampler.sample()
    sampler.save_samples("../{}/input_data/samples.txt".format(rpath))
    samples = pd.DataFrame(sampler.samples, columns = sampler.problem["names"])
    
    # Get the base data of the sets we are going to change and launch the baseline
    parameters = GSA_parameters(input_file = "../{}/input_data/input.csv".format(rpath))
    sets = parameters.load_sets()

    cmd1 = 'gams ./Balmorel_ReadData.gms --params="{}" s=s1'.format(sets)
    print("RUNNING:", cmd1, flush=True)
    rc1 = os.system(cmd1)

    if rc1 != 0:
        print("Balmorel_ReadData failed. See log below:\n", flush=True)
        os.system("tail -n 50 Balmorel_ReadData.lst")
        sys.exit(1)

    cmd2 = 'gams ./Balmorel_finish.gms --id=baseline --rpath={} r=s1 threads={}'.format(rpath, nb_cores-1)
    print("RUNNING:", cmd2, flush=True)
    rc2 = os.system(cmd2)

    if rc2 != 0:
        print("Balmorel_finish.gms baseline failed", flush=True)
        os.system("tail -n 50 Balmorel_finish.lst")
        sys.exit(1)
    
    # Loop for multi-core launch
    tic = time.time()
    pool = mp.Pool(processes = nb_cores-2)
    results = pool.starmap(run_scenario, [(index, sample, parameters, rpath) for index, sample in samples.iterrows()])
    pool.close()
    pool.join()

    tac = time.time()
    time_trajectory = tac-tic
    print("Time to create scenarios:", timedelta(seconds=time_trajectory))