#!/usr/bin/env bash
set -euo pipefail

# Resolve the SIF path relative to this script.
SINGULARITY_CMD="${SINGULARITY:-/cvmfs/oasis.opensciencegrid.org/mis/singularity/current/bin/singularity}"
echo "Using Singularity command: ${SINGULARITY_CMD}" >&2
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SIF_PATH="/cvmfs/singularity.opensciencegrid.org/eic/eic_ci:nightly"

#bind with gpfs02 only in local machine
#if pwd has /gpfs02/ then bind /gpfs02 ...to keep run_singularity.sh work in rcf machines as well
#if [[ "${PWD}" == /gpfs02/* ]]; then
#    export APPTAINER_BINDPATH="${APPTAINER_BINDPATH:+${APPTAINER_BINDPATH},},/cvmfs,${PWD},/gpfs02"
#else
#    export APPTAINER_BINDPATH="${APPTAINER_BINDPATH:+${APPTAINER_BINDPATH},}/cvmfs,${PWD}"
#fi

echo "Script args: $@" >&2

if [[ $# -gt 0 ]]; then
    ${SINGULARITY_CMD} exec "${SIF_PATH}" /bin/bash -lc "export PATH=/opt/local/bin:$PATH && exec \"\$@\"" bash "$@"
else
    ${SINGULARITY_CMD} exec "${SIF_PATH}" /bin/bash -lc "export PATH=/opt/local/bin:$PATH && exec /bin/bash"
fi
