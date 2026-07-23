# BIC/LowQ2 Framework

This is a testbed/prototype framework used in the initial versions of the
[BIC-MOBO](https://github.com/aid2e/BIC-MOBO) and [LowQ2-MOBO](https://github.com/aid2e/LowQ2-MOBO)
problems, and is superseded by the official [AID2E-framework](https://github.com/aid2e/AID2E-framework).


## Dependencies

- Ax 1.0.0+
- botorch
- Python 3.11+
- pip


## Quickstart

Install the framework:
```bash
# if using a python virtual environment
python -m venv .venv
source .venv/bin/activate
pip install git+https://github.com/aid2e/BICLowQ2-framework.git

# if using conda/mamba
conda create -n myenv python=3.11 pip
conda activate myenv
pip install git+https://github.com/aid2e/BICLowQ2-framework.git
```

Then see [BIC-MOBO](https://github.com/aid2e/BIC-MOBO) or
[LowQ2-MOBO](https://github.com/aid2e/LowQ2-MOBO) for example
usage.
