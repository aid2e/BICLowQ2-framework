# =============================================================================
## @file    OptionParser.py
#  @authors Derek Anderson
#  @date    07.22.2026
# -----------------------------------------------------------------------------
## @brief Module to parse commandline
#    options.
# =============================================================================

from typing import Any, Dict, Tuple
import argparse as ap
import os
import subprocess

from BICLowQ2.EICTools import ReadJsonFile


def GetConfigPath(config: str) -> str:
    """Get a configuration path

    Args:
      config: string indicating which path to retrieve
              (run, exp, par, obj)
    Returns:
      Path to config file as a string
    """
    path = None
    match config:
        case "run":
            path = os.getenv('RUN_CFG')
        case "exp":
            path = os.getenv('EXP_CFG')
        case "par":
            path = os.getenv('PAR_CFG')
        case "obj":
            path = os.getenv('OBJ_CFG')
        case _:
            raise ValueError(f"Unknown config file ({config}) specified!")
    return path


def GetConfigPaths() -> Tuple[str, ...]:
    """Get configuration paths

    Return paths to configuration files
    as a tuple of strings.
    """
    return (
        GetConfigPath('run'),
        GetConfigPath('exp'),
        GetConfigPath('par'),
        GetConfigPath('obj'),
    )


def LoadConfig(config: str) -> Dict[str, Any]:
    """Load a configuration file

    Args:
      config: string indicating which config to load
              (run, exp, par, obj)
    Returns:
      Loaded config file as a dictionary
    """
    path = GetConfigPath(config)
    data = ReadJsonFile(path)
    return data


def LoadConfigs() -> Tuple[Dict[str, Any], ...]:
    """Load configuration files

    Loads configuration files into dictionaries
    and returns them as a tuple.
    """
    return (
        LoadConfig('run'),
        LoadConfig('exp'),
        LoadConfig('par'),
        LoadConfig('obj'),
    )


def ParseArguments() -> ap.Namespace:
    """Parse arguments

    Instantiates an argparse.ArgumentParser object,
    updates relevant environment variables, and
    the filled Namespace.

    Supported args:
      -b: run in brute (manual sampling) mode
      -w: run in waves of jobs
      -r: specify runner
      -x: specify experiment to load
      -u: specify a run config to use
      -e: specify an experiment/problem config to use
      -p: specify a parameter config to use
      -o: specify an objective config to use
      -s: specify an environment script to source
      -t: specify a SLURM template to use
    Returns:
      argparse.Namespace object with attributes.
    """
    parser = ap.ArgumentParser()
    parser.add_argument("-b", "--brute", help = "Manually sample design space", action = 'store_true')
    parser.add_argument("-w", "--waves", help = "Run in waves of jobs", action = 'store_true')
    parser.add_argument("-r", "--runner", help = "Runner type", nargs = '?', const = 1, type = str, default = "joblib")
    parser.add_argument("-x", "--experiment", help = "JSON-serialized Ax experiment to load", nargs = '?', const = 1, type = str, default = None)
    parser.add_argument("-u", "--runconfig", help = "JSON config file for runtime options to use", nargs = '?', const = 1, type = str, default = None)
    parser.add_argument("-e", "--expconfig", help = "JSON config file for Ax options to use", nargs = '?', const = 1, type = str, default = None)
    parser.add_argument("-p", "--parconfig", help = "JSON config file for parameters to use", nargs = '?', const = 1, type = str, default = None)
    parser.add_argument("-o", "--objconfig", help = "JSON config file for objectives to use", nargs = '?', const = 1, type = str, default = None)
    parser.add_argument("-s", "--envscript", help = "Script to call to set environment variables", nargs = '?', const = 1, type = str, default = None)
    parser.add_argument("-t", "--template", help = "SLURM template to use", nargs = '?', const = 1, type = str, default = None)

    # grab arguments
    args = parser.parse_args()

    # if any config overrides provided,
    # update environment variables
    if args.runconfig is not None:
        os.environ['RUN_CFG'] = args.runconfig
    if args.expconfig is not None:
        os.environ['EXP_CFG'] = args.expconfig
    if args.parconfig is not None:
        os.environ['PAR_CFG'] = args.parconfig
    if args.objconfig is not None:
        os.environ['OBJ_CFG'] = args.objconfig

    # if an alternate environment script was provided,
    # run it
    if args.envscript is not None:
        mobo_this = args.envscript
        subprocess.run(f"source {mobo_this}", shell = True)

    return args


def GetMoboPath() -> str:
    """Get MOBO path

    Returns path to BIC-MOBO installation
    as a string.
    """
    return os.getenv('BIC_MOBO')


def GetThisMobo() -> str:
    """Get path to environment script

    Returns path to sourced BIC-MOBO
    environment script as a string.
    """
    return os.getenv('ENV_SCR')    


def GetSlurmTemplate() -> str:
    """Get path to SLURM template

    Returns path to SLURM job template
    as a string
    """
    return os.getenv('SLM_TMP')

# end =========================================================================
