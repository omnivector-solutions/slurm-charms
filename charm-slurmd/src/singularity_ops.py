import logging
import subprocess
from pathlib import Path
from slurm_ops_manager.utils import operating_system

logger = logging.getLogger()


class SingularityOps:
    """Singularity ops."""

    def __init__(self, charm):
        """Initialize class."""
        self._charm = charm

    def install(self, resource_path: Path):
        """Install singularity."""

        logger.debug(f"## Installing singularity from: {resource_path}")

        try:
            if operating_system() == 'ubuntu':
                self._install_deb(resource_path)
            else:
                self._install_rpm(resource_path)

            logger.debug("## Singularity successfully installed")

        except subprocess.CalledProcessError as e:
            logger.error(f"## Error installing singularity - {e}")

    def _install_deb(self, resource_path: Path):
        """Install on ubuntu using .deb"""

        cmd = f"apt install {resource_path} -y".split()
        subprocess.check_output(cmd)

    def _install_rpm(self, resource_path: Path):
        """Install on centos using .rpm"""

        cmd = f"yum localinstall {resource_path} -y".split()
        subprocess.check_output(cmd)
