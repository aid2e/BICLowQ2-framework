# =============================================================================
## @file    BICLowQ2Client.py
#  @authors Derek Anderson
#  @date    07.22.2026
# -----------------------------------------------------------------------------
## @brief Class to handle running, option parsing,
#    etc. for an optimization.
# =============================================================================

import json
import math
import os
import pathlib
import pickle
import re
import shutil
import subprocess

from ax.generation_strategy.generation_node import GenerationStep
from ax.generation_strategy.generation_strategy import GenerationStrategy
from ax.modelbridge.registry import Generators
from ax.service.ax_client import AxClient
from ax.service.utils.report_utils import exp_to_df
from scheduler import AxScheduler, JobLibRunner, SlurmRunner

from BICLowQ2.AID2ETools import OptionParser

class BICLowQ2Client:
    """AID2EClient

    A class to handle running, options, etc. for an
    optimization. Key functionality:

    Run   -- run an optimization with a single monitoring job
    Waves -- run optimization over several waves of jobs with
             a sequence of monitoring jobs
    Brute -- run trial/objective function on provided list
             of design points

    Note that custom Ax generation strategies can be
    used by provided it as an argument during initialization.

    Attributes:
      objective:  trial/objective function to run
      arguments:  parsed command line options (argparse.Namespace)
      generation: Ax generation strategy to use (optional)

    Usage:
      >>> def my_objective():
      ...     return 0.5
      >>> options = BICLowQ2.AID2ETools.ParseArguments()
      >>> client  = BICLowQ2Client(options, my_objective)
      >>> # run with a single monitoring job
      >>> client.Run()
      >>> # run in sequence of monitoring job
      >>> client.Waves("this_file_calls_client_run.py")
      >>> # run "brute force" search through list of design points
      >>> params = [
      ...     {"par_a": 0, "par_b": 1},
      ...     {"par_a": 1, "par-b": 0},
      ... ]
      >>> client.Brute(params)
    """

    def __init__(self, args, obj, gen = None):
        """Constructor accepting arguments

        Args:
          args: parsed command line options (argparse.Namespace)
          obj:  objective function/function to run each trial
          gen:  ax generation strategy
                (ax.generation_strategy.generation_strategy.GenerationStrategy)
        """
        self.arguments  = args
        self.objective  = obj
        self.generation = gen

    def _GetWaveCfgName(self, iwave, wavedir, config):
        """GetWaveCfgName

        Helper method to construct name of
        experiment config file for a wave.

        Args:
          iwave:   wave index
          wavedir: directory to store wave files
          config:  string indicating config file to load
        Returns:
          Created config file name (with path!)
        """
        cfg_path = pathlib.Path(OptionParser.GetConfigPath(config))
        cfg_name = cfg_path.name.replace('.config', f'_{iwave}.config')
        cfg_wave = f"{wavedir}/{cfg_name}"
        return cfg_wave

    def _MakeWaveExpConfig(self, iwave, nparallel, ntotal, wavedir):
        """MakeWaveExpConfig

        Helper method to generate an experiment
        config file for a wave.

        Args:
          iwave:     wave index
          nparallel: no. of trials to run in parallel
          ntotal:    total no. of trials to run
          wavedir:   directory to store wave files
        Returns:
          Path to created config file
        """
        # load base config file, calculate max no. of
        # trials for wave
        cfg_data = OptionParser.LoadConfig('exp')
        exp_name = cfg_data['problem_name']
        exp_out  = cfg_data['OUTPUT_DIR']
        nfront   = min((iwave + 1) * nparallel, ntotal)

        # update wave, n_max_trials, output dir
        cfg_data['problem_name'] = f"{exp_name}_{iwave}"
        cfg_data['OUTPUT_DIR']   = f"{exp_out}/wave_{iwave}"
        cfg_data['n_max_trials'] = nfront

        # dump updated config to wave directory
        cfg_wave = self._GetWaveCfgName(iwave, wavedir, 'exp')
        with open(cfg_wave, "w") as cfg:
            json.dump(cfg_data, cfg, indent = 4)

        # return path to created wave config
        return cfg_wave

    def _MakeWaveRunConfig(self, iwave, wavedir):
        """MakeWaveRunConfig

        Helper method to generate a runtime
        config file for a wave.

        Args:
          iwave:   wave index
          wavedir: directory to store wave output
        Returns:
          Path to created config file
        """
        # load base config file
        cfg_data = OptionParser.LoadConfig('run')
        run_out  = cfg_data['out_path']
        run_dir  = cfg_data['run_path']

        # update directories
        cfg_data['out_path'] = f"{run_out}/wave_{iwave}"
        cfg_data['run_path'] = f"{run_dir}/wave_{iwave}"

        # dump updated config to wave directory
        cfg_wave = self._GetWaveCfgName(iwave, wavedir, 'run')
        with open(cfg_wave, "w") as cfg:
            json.dump(cfg_data, cfg, indent = 4)

        # return path to created wave config
        return cfg_wave

    def _GetJobID(self, stdout):
        """GetJobID

        Helper method to extract Job ID from
        SLURM submission message.

        Args:
          stdout: stripped stdout from subprocess
        Returns:
          Job ID on successful extraction
        Raises:
          RunTimeError if job id not able to be extracted
        """
        match = re.search(r"Submitted batch job (\d+)", stdout)
        if match:
            return match.group(1)
        else:
            raise RuntimeError(f"Couldn't extract JobID from stdout:\n{stdout}")

    def Waves(self, main):
        """Run in waves of jobs

        Run MOBO in waves via slurm. The no. and size of waves
        are determined by n_max_trials and max_parallel_gen to
        avoid time limits on slurm jobs.

        Note:
          The user needs to provide a path to the file which
          calls BICLowQ2Client.Run()! The client will create
          submission scripts which attempt to run
              >>> python the_file.py <arguments>

        Args:
          main: file which calls BICLowQ2Client.Run()
        """

        # load relevant config and extract no. of parallel
        # and total trials to run
        run_cfg   = OptionParser.LoadConfig('run')
        exp_cfg   = OptionParser.LoadConfig('exp')
        nparallel = exp_cfg['max_parallel_gen']
        ntotal    = exp_cfg['n_max_trials']
        nwave     = math.ceil(ntotal / nparallel)

        # create and submit a pilot job for each wave
        prevjob = None
        prevexp = None
        for iwave in range(0, nwave):

            # create a directory to hold wave files
            wavedir = run_cfg['run_path'] + f"/wave_{iwave}"
            if os.path.isdir(wavedir):
                shutil.rmtree(wavedir)
                os.mkdir(wavedir)
            else:
                os.mkdir(wavedir)

            # create config files and experiment output to use for wave
            wave_exp = self._MakeWaveExpConfig(iwave, nparallel, ntotal, wavedir)
            wave_run = self._MakeWaveRunConfig(iwave, wavedir)
            prev_exp = None
            if iwave > 0:
                with open(prevexp, 'r') as data:
                    exp_data = json.load(data)
                    prev_exp = f"{exp_data['OUTPUT_DIR']}/{exp_data['problem_name']}_exp_out.json"

            # set output & error logs
            out = f"--output={run_cfg['log_path']}/pilot_{iwave}.out"
            err = f"--error={run_cfg['log_path']}/pilot_{iwave}.err"

            # copy slurm template to wave directory
            slpath = wavedir + f"/wave_{iwave}.sh"
            shutil.copyfile(OptionParser.GetSlurmTemplate(), slpath)

            # append additional commands to slurm script
            with open(slpath, 'a') as script:

                # add output/error options
                script.write(f"#SBATCH {out}\n")
                script.write(f"#SBATCH {err}\n")

                # write command
                if iwave > 0:
                    script.write(f"\npython {main} -r slurm -e {wave_exp} -u {wave_run} -x {prev_exp}")
                else:
                    script.write(f"\npython {main} -r slurm -e {wave_exp} -u {wave_run}")

                # make script executable
                os.chmod(slpath, 0o777)

                # submit job and make it dependent on
                # previous wave completing
                output = None
                if iwave > 0:
                    output = subprocess.run(['sbatch', f'--dependency=afterok:{prevjob}', f'{slpath}'], capture_output = True, text = True)
                else:
                    output = subprocess.run(['sbatch', f'{slpath}'], capture_output = True, text = True)

                # throw error if something went wrong, otherwise extract
                # job id and store experiment config for next wave
                if output.returncode != 0:
                    raise RuntimeError(f"Error while submitting wave {iwave}: return code {output.returncode}")
                else:
                    prevexp = wave_exp
                    prevjob = GetJobID(output.stdout.strip())

    def Run(self):
        """Run single monitoring job

        Runs MOBO with a single monitoring job. The model and
        generation strategy are saved to both JSON and CSV files
        (model) and pickle files (generation) for downstream
        analysis.

        Note:
          See BICLowQ2.AID2ETools.OptionParser for a detailed list
          of supported command line arguments.
        """

        # load relevant config files
        run_cfg, exp_cfg, par_cfg, obj_cfg = OptionParser.LoadConfigs()

        # translate parameter, objective options
        # into ax-compliant ones
        ax_pars, ax_par_cons = at.ConvertParamConfig(par_cfg)
        ax_objs, ax_obj_cons = at.ConvertObjectConfig(obj_cfg)

        # define generation strategy to use
        #   --> if none provided when initializing client,
        #       use default!
        gstrat = None
        if self.generation is None:
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
        else:
            gstart = self.generation

        # either create or load ax experiment as needed
        ax_client = None
        if self.arguments.experiment == None:
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
            if os.path.isfile(self.arguments.experiment):
                ax_client = AxClient().load_from_json_file(self.arguments.experiment)
            else:
                raise FileNotFoundError(f"File {self.arguments.experiment} not found!")

        # set up runners
        runner = None
        match self.arguments.runner:
            case "joblib":
                runner = JobLibRunner(
                    n_jobs = run_cfg["sched_n_jobs"],
                    config = {
                        'tmp_dir' : run_cfg["run_path"]
                    }
                )
            case "slurm":
                runner = SlurmRunner(
                    slurm_template = f"{OptionParser.GetSlurmTemplate()}",
                    init_env = [
                        f"source {OptionParser.GetThisMobo()}",
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
        scheduler.set_objective_function(OptionParser.RunObjectives)

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


    def Brute(self, params):
        """Run specific parameterizations

        Alternative method to run MOBO. Eschews Ax to instead manually
        sample a set of specific parameterizations.

        Parameterizations must be provided as a list of dictionaries
        in the format:
            >>> [{'param_a_name': <value>, 'param_b_name': <value>, ...},
            ...  {'param_a_name': <value>, 'param_b_name': <value>, ...},
            ...  etc]

        Note:
          User can override which configuration files
          to use with the -u, -p, -o, -s, -t options
          as detailed in BICLowQ2.AID2ETools.OptionParser.

        Args:
          params: a list of parameterizations to run
        """

        # create and run a Slurm job for each parameterization
        itrial = 0
        for param in params:

            # create trial tag and argument
            tag    = f"BrutTrial{itrial}"
            tagarg = f"--tag {tag}"

            # set ouput & error logs
            out = f"--output={run_cfg['log_path']}/{tag}.out"
            err = f"--error={run_cfg['log_path']}/{tag}.err"

            # copy slurm template to run directory
            slpath = run_cfg["run_path"] + f"/Run{tag}.sh"
            shutil.copyfile(itf.GetSlurmTemplate(), slpath)

            # append additional commands to slurm script
            with open(slpath, 'a') as script:

                # add output/error options
                script.write(f"#SBATCH {out}\n")
                script.write(f"#SBATCH {err}\n")

                # construct arguments for objective runner
                kwargs = f"{tagarg}"
                for parkey, parval in param.items():
                    kwargs += f" --{parkey} {parval}"

                # now add line to run objective runner
                # with arguments
                script.write(f"\npython {obj_run} {kwargs}")
        
            # make script executable and submit it
            os.chmod(slpath, 0o777)
            subprocess.run(["sbatch", slpath])
            itrial += 1

# end =========================================================================
