"""
AID2E Tools (Test ver.)

A testbed library for AID2E tools so
simplify interfacing with Ax, etc.
"""

__version__="0.0.0"

from .AxHelper import *

__all__ = [
    "ConvertParamConfig",
    "ConverParamList",
    "ConvertObjectConfig",
    "CreateObjectiveNames"
]
