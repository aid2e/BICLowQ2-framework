import logging
from itertools import product
import sys,argparse

import AID2ETestTools as att
import EICMOBOTestTools as emt

# Global parameters here (Only needed for multi-step jobs)
global_parameters = {}



def RunObjectives(*args, **kwargs):
    """Wrapper for RunObjectives from interfaces.RunObjectives
    
    This function creates a trial tag and calls the main
    RunObjectives implementation, then formats the return
    value for the scheduler.
    
    Args:
        *args: positional arguments (unused)
        **kwargs: keyword arguments containing trial parameters
        
    Returns:
        dict: dictionary of objectives for the scheduler
    """
    import datetime
    import re
    from interfaces.RunObjectives import RunObjectives as RunObjectivesImpl
    
    # Log start of trial with parameters
    print(f"\n{'='*80}")
    print(f"Starting RunObjectives with parameters: {kwargs}")
    print(f"{'='*80}\n")
    
    # create tag for trial
    time = str(datetime.datetime.now())
    time = re.sub(r'[.\-:\ ]', '', time)
    tag = f"AxTrial{time}"
    
    # Call the main implementation
    # TODO - Check the RunObjectivesImpl function to see if it needs the tag or other parameters, and pass them accordingly
    objectives = RunObjectivesImpl(tag=tag, **kwargs)
    
    print(f"Objectives returned: {objectives}")
    
    # For backward compatibility with scheduler expecting "objective" key,
    # if there's only one objective, return it as "objective"
    # Otherwise return the full dictionary
    #  FIXME - This needs to be verified that single objective is expected to be returned as "objective" key.
    return objectives if len(objectives) > 1 else {"objective": list(objectives.values())[0]}



# The main function to be called by the Panda runner
if __name__ == "__main__":
    """Panda BIC-MOBO main

    Main function to be called by
    the Panda runner to execute BIC-MOBO.
    """
    #import the ax-related modules here
    import getpass, os
    from ax.service.ax_client import AxClient, ObjectiveProperties
    from ax.modelbridge.registry import Generators
    from ax.modelbridge.generation_strategy import GenerationStrategy, GenerationStep
    #from ax.generation_strategy import GenerationStrategy, GenerationStep
    from scheduler.utils.common import setup_logging
    from scheduler.job.job import JobType
    from scheduler import AxScheduler, JobLibRunner, PanDAiDDSRunner

    # setup logging
    #Available levels: "debug", "info", "warning", "error", "critical"
    setup_logging(log_level="debug")

    # Now create the experiment
    logging.info("Create the experiment")
    # parameters are the detector parameters to be optimized.
    # I will assume that the main path is given by the environemnt variable AIDE_WORKDIR
    main_path = os.getenv("AIDE_WORKDIR", os.getcwd())
    # Config file paths
    par_path = os.path.join(main_path, "configuration/parameters.config")
    obj_path = os.path.join(main_path, "configuration/objectives.config")
    exp_path = os.path.join(main_path, "configuration/problem.config")


    cfg_par = emt.ReadJsonFile(par_path)
    cfg_obj = emt.ReadJsonFile(obj_path)
    # Get the configuration parameters from the json file
    cfg_exp = emt.ReadJsonFile(exp_path)
    logging.debug("Initializing the ax client")

    gstrat = GenerationStrategy(
        steps=[
        GenerationStep(model=Generators.SOBOL, num_trials=cfg_exp["n_sobol"],min_trials_observed=cfg_exp["min_sobol"], max_parallelism=cfg_exp["n_sobol"]),
        GenerationStep(model=Generators.BOTORCH_MODULAR, num_trials=-1, max_parallelism=cfg_exp["max_parallel_gen"])
    ]
    )
    ax_client = AxClient(generation_strategy=gstrat)

    cfg_par, cfg_par_cons = att.ConvertParamConfig(cfg_par)
    cfg_obj, cfg_obj_cons = att.ConvertObjectConfig(cfg_obj)
    # print the configuration parameters and objectives
    print("Configuration parameters: ", cfg_par)
    print("Configuration objectives: ", cfg_obj)
    print("Configuration parameter constraints: ", cfg_par_cons)
    print("*****************************************************************")
    ax_client.create_experiment(
        name="BIC-MOBO-Panda-Experiment",
        parameters = cfg_par,
        objectives = cfg_obj,
        parameter_constraints = cfg_par_cons
        )

    # Now need to initialize the environment for the Panda runner
    # setup_mamba contains ax related environment that might be neded during a PanDA job. 
    logging.info("Initializing the environment for the Panda runner")
    # TODO - Still need to verify that this initialization is correct. Tested locally but not in remote cluster as PanDA job.
    init_env = [
        "command -v singularity &> /dev/null || export SINGULARITY=/cvmfs/oasis.opensciencegrid.org/mis/singularity/current/bin/singularity;",
        "export AIDE_WORKDIR=$(pwd);",
        "export SIF=/cvmfs/singularity.opensciencegrid.org/eic/eic_ci:nightly;",
        "echo AIDE_WORKDIR: ${AIDE_WORKDIR};",

        # Install micromamba (minimal)
        "export MAMBA_ROOT_PREFIX=${AIDE_WORKDIR}/micromamba;",
        "export MAMBA_EXE=${MAMBA_ROOT_PREFIX}/bin/micromamba;",
        "mkdir -p ${MAMBA_ROOT_PREFIX}/bin;",
        'curl -Ls https://micromamba.snakepit.net/api/micromamba/linux-64/latest | tar -xj -C ${MAMBA_ROOT_PREFIX} bin/micromamba;',
        "chmod -R a+rx ${MAMBA_ROOT_PREFIX};",
        # Install Python 3.13
        "${MAMBA_EXE} install -y -r ${MAMBA_ROOT_PREFIX} -n base -c conda-forge python=3.13;",
        "${MAMBA_EXE} clean -a -y;",
        # Activate micromamba and install packages via pip
        'eval \"$(${MAMBA_EXE} shell hook -s posix)\";',
        "micromamba activate base;",
        "pip install pandas seaborn botorch ax-platform==1.0.0 numpy matplotlib torch;",

        # Make sure to use mamba python
        'export PATH=${MAMBA_ROOT_PREFIX}/bin:$PATH;',

        # Echo python being used
        'echo \"python version being used\" $(python --version; which python);',

        # Clone epic
        "git clone --depth 1 https://github.com/eic/epic.git ${AIDE_WORKDIR}/epic;",

        # Create build/install dirs WITHOUT changing cwd
        "mkdir -p ${AIDE_WORKDIR}/epic/build ${AIDE_WORKDIR}/epic/install;",

        # Build epic inside singularity WITHOUT cd side-effects
        '${SINGULARITY} exec --bind ${AIDE_WORKDIR}:${AIDE_WORKDIR} ${SIF} /bin/bash -c "cmake -B ${AIDE_WORKDIR}/epic/build -S ${AIDE_WORKDIR}/epic -DCMAKE_INSTALL_PREFIX=${AIDE_WORKDIR}/epic/install && cmake --build ${AIDE_WORKDIR}/epic/build && cmake --install ${AIDE_WORKDIR}/epic/build";',

        # Singularity setup
        'export SINGULARITY_OPTIONS="--bind /cvmfs:/cvmfs,${AIDE_WORKDIR}:${AIDE_WORKDIR}";',
        "export SIF=/cvmfs/singularity.opensciencegrid.org/eic/eic_ci:nightly;",
        "export SINGULARITY_BINDPATH=/cvmfs;",

        # Set MOBO path
        "export BIC_MOBO=${AIDE_WORKDIR};",
        "echo BIC_MOBO path: $BIC_MOBO;",

        'echo "END OF ENVIRONMENT SETUP";',
    ]
    init_env = " ".join(init_env)

    #Now create panda_attr dictionary
    dset_name_prefix = "user."+getpass.getuser()+".bic-mobo-panda-idds"
    panda_attrs = {
        "name": dset_name_prefix,
        "init_env": init_env,
        "cloud": "US",
        "queue": "BNL_PanDA_1", # Test runs locally # Other options are BNL_OSG_PanDA_2, BNL_OSG_PanDA_1, BNL_PanDA_1, BNL_PanDA_2
        "source_dir":None,
        "source_dir_parent_level":1,
        "exclude_source_files":[
            r"(^|/)\.[^/]+", # hidden files and directories
            r"(^|/)out(/|$)",# directories called out and run are excluded
            r"(^|/)run(/|$)",
            r"(^|/)share(/|$)",
            r"(^|/)calibrations(/|$)",
            r"(^|/)fieldmaps(/|$)",
            r"(^|/)gdml(/|$)",
            r"(^|/)epic(/|$)",
            "doc*",
            ".*log","examples","scheduler_epic",
            ".*txt","__pycache__" # calibrations dir has sym links
        ],
        "max_walltime":3600,
        "core_count":2,
        "total_memory":8000,
        "enable_separate_log":True,
        "job_dir":None,
    }

    #Create panda runner
    print("Creating PanDA iDDS runner")
    runner = PanDAiDDSRunner(**panda_attrs)
    logging.info("Creating scheduler for a simple panda job")
    scheduler = AxScheduler(ax_client, runner)
    #set the objective
    scheduler.set_objective_function(RunObjectives)
    logging.info("Starting the optimization")
    # FIXME Jobs are not landing in the queue. Cannot find job information in pandamon. Tested with a simple panda test function as well....
    best_param = scheduler.run_optimization(max_trials=cfg_exp["n_max_trials"])
    print("best parameters: ", best_param)