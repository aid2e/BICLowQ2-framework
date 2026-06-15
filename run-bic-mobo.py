# =============================================================================
## @file   run-bic-mobo.py
#  @author Derek Anderson
#  @date   09.25.2025
# -----------------------------------------------------------------------------
## @brief Main executable and wrapper script for
#    running the BIC-MOBO problem.
# =============================================================================

import json
import os
import pickle

from ax.generation_strategy.generation_node import GenerationStep
from ax.generation_strategy.generation_strategy import GenerationStrategy
from ax.service.ax_client import AxClient
from ax.service.utils.report_utils import exp_to_df
from scheduler import AxScheduler, JobLibRunner, SlurmRunner

import AID2ETestTools as att
import interfaces as itf

def main(*args, **kwargs):
    """main

    Wrapper to run BIC-MOBO. The model
    and generation strategy are saved
    to both JSON and CSV files (model)
    and pickle files (generation) for
    downstream analysis.

    User can specify which runner to use
    with the -r option:

      joblib -- use joblib runner (default)
      slurm  -- use slurm runner
      panda  -- use panda runner (TODO)

    User can also specify an Ax experiment
    to load with the -x option, or override
    which configuration files to use with the
    -u, -e, -p, -o, -s, -t options as detailed
    below.

    Args:
      -r: specify runner
      -x: specify experiment to load
      -u: specify a run config to use
      -e: specify an experiment/problem config to use
      -p: specify a parameter config to use
      -o: specify an objective config to use
      -s: specify an environment script to source
      -t: specify a SLURM template to use
    """

    # parse argsuments
    args = itf.ParseArguments()
    if os.getenv('BIC_MOBO') == None:
        raise EnvironmentError("BIC_MOBO environment variable not set!")

    # load relevant config files
    run_cfg, exp_cfg, par_cfg, obj_cfg = itf.LoadConfigs()

    # translate parameter, objective options
    # into ax-compliant ones
    ax_pars, ax_par_cons = att.ConvertParamConfig(par_cfg)
    ax_objs, ax_obj_cons = att.ConvertObjectConfig(obj_cfg)

    # define generation strategy to use
    gstrat = GenerationStrategy(
        steps = [
            GenerationStep(
                model = Generators.SOBOL,
                num_trials = exp_cfg["n_sobol"],
                min_trials_observed = exp_cfg["min_sobol"],
                max_parallelism = exp_cfg["max_parallel_gen"]
            ),
            GenerationStep(
                model = Generators.BOTORCH_MODULAR,
                num_trials = -1,
                max_parallelism = exp_cfg["max_parallel_gen"]
            )
        ]
    )

    # either create or load ax experiment as needed
    ax_client = None
    if args.experiment == None:
        ax_client = AxClient(
            generation_strategy = gstrat,
            enforce_sequential_optimization = False
        )
        ax_client.create_experiment(
            name = exp_cfg["problem_name"],
            parameters = ax_pars,
            objectives = ax_objs,
            parameter_constraints = ax_par_cons
        )
    else:
        if os.path.isfile(args.experiment):
            ax_client = AxClient().load_from_json_file(args.experiment)
        else:
            raise FileNotFoundError(f"File {args.experiment} not found!")

    # set up runners
    runner = None
    match args.runner:
        case "joblib":
            runner = JobLibRunner(
                n_jobs = run_cfg["sched_n_jobs"],
                config = {
                    'tmp_dir' : run_cfg["run_path"]
                }
            )
        case "slurm":
            runner = SlurmRunner(
                slurm_template = f"{itf.GetSlurmTemplate()}",
                init_env = [
                    f"source {itf.GetThisMobo()}",
                    f"source {run_cfg['conda']}",
                    f"conda activate {run_cfg['environment']}",
                    "conda list"
                ]
            )
        case _:
            raise ValueError("Unknown runner specified!")

    # set up scheduler
    scheduler = AxScheduler(
        ax_client,
        runner,
        config = {
            'job_output_dir' : exp_cfg["OUTPUT_DIR"],
            'max_concurrent_trials' : exp_cfg["max_parallel_gen"],
            'enable_checkpoint' : True,
            'monitoring_interval' : run_cfg["monitoring_interval"],
        }
    )
    scheduler.set_objective_function(itf.RunObjectives)

    # run and report best parameters
    best = scheduler.run_optimization(max_trials = exp_cfg["n_max_trials"])
    print(f"Optimization complete! Best parameters:\n", best)

    # create paths to output files
    oPathBase = exp_cfg["OUTPUT_DIR"] + "/" + exp_cfg["problem_name"]
    oPathCSV  = oPathBase + "_exp_out.csv"
    oPathJson = oPathBase + "_exp_out.json"
    oPathPikl = oPathBase + "_gen_out.pkl"
    oPathBest = oPathBase + "_best_params.json"

    # save optimal prameters to a json file
    with open(oPathBest, 'w') as file:
        json.dump(best, file)

    # grab experiment and generation strategy
    # for output
    exp   = ax_client._experiment
    gen   = ax_client._generation_strategy
    dfExp = exp_to_df(exp)

    # save outcomes and experiment
    # for downstream analysis
    dfExp.to_csv(oPathCSV)
    ax_client.save_to_json_file(oPathJson)
    with open(oPathPikl, 'wb') as file:
        pickle.dump(gen.model, file)

if __name__ == "__main__":
   main()

# end =========================================================================
