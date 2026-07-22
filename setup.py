# =============================================================================
## @file   setup.py
#  @author Derek Anderson
#  @date   07.21.2026
# -----------------------------------------------------------------------------
## @brief Setup script for easy installation
#    of framework
# =============================================================================

from setuptools import find_packages, setup

setup(
    name = 'bic-lowq2-framework',
    version = '0.0.0',
    packages = find_packages(where = "src"),
    package_dir = {"": "src"},
    install_requires = [
        "ax-platform==1.0.0",
        "botorch",
        "torch",
    ],
)

# end =========================================================================
