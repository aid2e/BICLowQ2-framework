# =============================================================================
## @file   launch-mobo.py
#  @author Derek Anderson
#  @date   04.23.2026
# -----------------------------------------------------------------------------
## @brief Launches a sequence of slurm pilot jobs and
#    generates relevant problem.config, environment
#    scripts.
# =============================================================================

import json
import math
import os
import pathlib
import re
import shutil
import subprocess

import interfaces as itf

def GetWaveCfgName(iwave, wavedir, config):
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
    cfg_path = pathlib.Path(itf.GetConfigPath(config))
    cfg_name = cfg_path.name.replace('.config', f'_{iwave}.config')
    cfg_wave = f"{wavedir}/{cfg_name}"
    return cfg_wave

def MakeWaveExpConfig(iwave, nparallel, ntotal, wavedir):
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
    cfg_data = itf.LoadConfig('exp')
    exp_name = cfg_data['problem_name']
    exp_out  = cfg_data['OUTPUT_DIR']
    nfront   = min((iwave + 1) * nparallel, ntotal)

    # update wave, n_max_trials, output dir
    cfg_data['problem_name'] = f"{exp_name}_{iwave}"
    cfg_data['OUTPUT_DIR']   = f"{exp_out}/wave_{iwave}"
    cfg_data['n_max_trials'] = nfront

    # dump updated config to wave directory
    cfg_wave = GetWaveCfgName(iwave, wavedir, 'exp')
    with open(cfg_wave, "w") as cfg:
        json.dump(cfg_data, cfg, indent = 4)

    # return path to created wave config
    return cfg_wave

def MakeWaveRunConfig(iwave, wavedir):
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
    cfg_data = itf.LoadConfig('run')
    run_out  = cfg_data['out_path']
    run_dir  = cfg_data['run_path']

    # update directories
    cfg_data['out_path'] = f"{run_out}/wave_{iwave}"
    cfg_data['run_path'] = f"{run_dir}/wave_{iwave}"

    # dump updated config to wave directory
    cfg_wave = GetWaveCfgName(iwave, wavedir, 'run')
    with open(cfg_wave, "w") as cfg:
        json.dump(cfg_data, cfg, indent = 4)

    # return path to created wave config
    return cfg_wave

def GetJobID(stdout):
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

def main(*args, **kwargs):
    """main

    Wrapper to run BIC-MOBO via slurm. Runs
    the problem in waves determined by
    n_max_trials and max_parallel_gen to
    avoid time limits on slurm jobs.
    """
    # parse argsuments
    args = itf.ParseArguments()

    # load relevant config and extract no. of parallel
    # and total trials to run
    run_cfg   = itf.LoadConfig('run')
    exp_cfg   = itf.LoadConfig('exp')
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
        wave_exp = MakeWaveExpConfig(iwave, nparallel, ntotal, wavedir)
        wave_run = MakeWaveRunConfig(iwave, wavedir)
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
        shutil.copyfile(itf.GetSlurmTemplate(), slpath)

        # append additional commands to slurm script
        with open(slpath, 'a') as script:

            # add output/error options
            script.write(f"#SBATCH {out}\n")
            script.write(f"#SBATCH {err}\n")

            # write command
            if iwave > 0:
                script.write(f"\npython {itf.GetMoboPath()}/run-bic-mobo.py -r slurm -e {wave_exp} -u {wave_run} -x {prev_exp}")
            else:
                script.write(f"\npython {itf.GetMoboPath()}/run-bic-mobo.py -r slurm -e {wave_exp} -u {wave_run}")

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

if __name__ == "__main__":
   main()

# end =========================================================================
