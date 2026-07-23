# =============================================================================
## @file    EnvironmentManager.py
#  @authors Derek Anderson
#  @date    07.22.2026
# -----------------------------------------------------------------------------
# @brief Module to manage conda/mamba environments
#   and environment variables.
# =============================================================================

import os
import subprocess

def MakeThisMoboScripts(path: str) -> None:
    """MakeThisMoboScripts

    Generates scripts to set environment
    variables and places them in path/bin

    Args:
      path: directory to create and place files in 
    """

    # csh script body
    csh = '#!/bin/csh\n' \
          'set invoked = ($_)\n' \
          'if ("$invoked" != "") then\n' \
          '    set path_to_this = `readlink -f "$invoked[2]:q"`\n' \
          'else\n' \
          '    set path_to_this = `readlink -f "$0:q"`\n' \
          'endif\n' \
          'setenv THIS_MOBO "${path_to_this:h:h}"\n' \
          'setenv OBJ_CFG "$THIS_MOBO/configuration/objectives.config"\n' \
          'setenv PAR_CFG "$THIS_MOBO/configuration/parameters.config"\n' \
          'setenv EXP_CFG "$THIS_MOBO/configuration/problem.config"\n' \
          'setenv RUN_CFG "$THIS_MOBO/configuration/run.config"\n' \
          'setenv SLM_TMP "$THIS_MOBO/configuration/template.slurm"\n' \
          'setenv ENV_SCR "$THIS_MOBO/bin/this-mobo.csh"'

    # sh script body
    sh = '#!/bin/sh\n' \
         'path_to_this=$(cd -P -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)\n' \
         'export THIS_MOBO=$(dirname -- "$path_to_this")\n' \
         'export OBJ_CFG=$THIS_MOBO/configuration/objectives.config\n' \
         'export PAR_CFG=$THIS_MOBO/configuration/parameters.config\n' \
         'export EXP_CFG=$THIS_MOBO/configuration/problem.config\n' \
         'export RUN_CFG=$THIS_MOBO/configuration/run.config\n' \
         'export SLM_TMP=$THIS_MOBO/configuration/template.slurm\n' \
         'export ENV_SCR=$THIS_MOBO/bin/this-mobo.sh'

    # tcsh script body
    tcsh = '#!/bin/tcsh\n' \
           'set invoked = ($_)\n' \
           'if ("$invoked" != "") then\n' \
           '    set path_to_this = `readlink -f "$invoked[2]:q"`\n' \
           'else\n' \
           '    set path_to_this = `readlink -f "$0:q"`\n' \
           'endif\n' \
           'setenv THIS_MOBO "${path_to_this:h:h}"\n' \
           'setenv OBJ_CFG "$THIS_MOBO/configuration/objectives.config"\n' \
           'setenv PAR_CFG "$THIS_MOBO/configuration/parameters.config"\n' \
           'setenv EXP_CFG "$THIS_MOBO/configuration/problem.config"\n' \
           'setenv RUN_CFG "$THIS_MOBO/configuration/run.config"\n' \
           'setenv SLM_TMP "$THIS_MOBO/configuration/template.slurm"\n' \
           'setenv ENV_SCR "$THIS_MOBO/bin/this-mobo.tcsh"'

    # zsh script body
    zsh = '#!/bin/zsh\n' \
          'set -f\n' \
          'path_to_this="${(%):-%N}"\n' \
          'export THIS_MOBO="${path_to_this:A:h:h}"\n' \
          'export OBJ_CFG=$THIS_MOBO/configurations/objectives.config\n' \
          'export PAR_CFG=$THIS_MOBO/configuration/parameters.config\n' \
          'export EXP_CFG=$THIS_MOBO/configuration/problem.config\n' \
          'export RUN_CFG=$THIS_MOBO/configuration/run.config\n' \
          'export SLM_TMP=$THIS_MOBO/configuration/template.slurm\n' \
          'export ENV_SCR=$THIS_MOBO/bin/this-mobo.sh'

    # create bin directory if it doesn't exist
    place = f"{path}/bin"
    if not os.path.isdir(place):
        os.makedirs(place)

    # create scripts
    cplace = f"{place}/this-mobo.csh"
    with open(cplace, 'w') as this:
        this.write(csh)

    splace = f"{place}/this-mobo.sh"
    with open(splace, 'w') as this:
        this.write(sh)

    tplace = f"{place}/this-mobo.tcsh"
    with open(tplace, 'w') as this:
        this.write(tcsh)

    zplace = f"{place}/this-mobo.zsh"
    with open(zplace, 'w') as this:
        this.write(zsh)

    # modify permissions
    os.chmod(cplace, 0o777)
    os.chmod(splace, 0o777)
    os.chmod(tplace, 0o777)
    os.chmod(zplace, 0o777)
    print(f"Created this-mobo scripts at {place}")

# end =========================================================================
