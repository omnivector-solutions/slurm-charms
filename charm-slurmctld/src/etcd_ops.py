"""etcd operations."""

import json
import logging
import shlex
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import List

from etcd3gw.client import Etcd3Client

logger = logging.getLogger()


class EtcdOps:
    """ETCD ops."""

    def __init__(self):
        """Initialize class."""
        # system user and group
        self._etcd_user = "etcd"
        self._etcd_group = "etcd"
        self._etcd_service = "etcd.service"

    def install(self, resource_path: Path):
        """Install etcd."""
        # extract resource tarball
        with TemporaryDirectory(prefix="omni") as tmp_dir:
            logger.debug(f"## extracting {resource_path} to {tmp_dir}")
            with tarfile.open(resource_path, 'r') as tar:
                tar.extractall(path=tmp_dir)

            usrbin = Path("/usr/bin")
            logger.debug(f"## installing etcd in {usrbin}")
            source = Path(tmp_dir) / "etcd-v3.5.0-linux-amd64"
            for abin in ["etcd", "etcdutl", "etcdctl"]:
                shutil.copy2(source / abin, usrbin / abin)

        self._create_etcd_user_group()

        varlib = Path("/var/lib/etcd")
        if not varlib.exists():
            varlib.mkdir()
        shutil.chown(varlib, user=self._etcd_user, group=self._etcd_group)

        self._setup_systemd()

    def _create_etcd_user_group(self):
        logger.debug("## creating etcd user and group")
        cmd = f"groupadd {self._etcd_group}"
        subprocess.call(shlex.split(cmd))

        subprocess.call(["useradd",
                         "--system",
                         "--no-create-home",
                         f"--gid={self._etcd_group}",
                         "--shell=/usr/sbin/nologin",
                         self._etcd_user])

    def _setup_systemd(self):
        logger.debug("## creating systemd files for etcd")

        charm_dir = Path(__file__).parent
        template_dir = Path(charm_dir) / "templates"
        source = template_dir / "etcd.service.tmpl"
        dest = Path("/etc/systemd/system/") / self._etcd_service
        shutil.copy2(source, dest)

        subprocess.call(["systemctl", "daemon-reload"])

    def start(self):
        """Start etcd service."""
        logger.debug("## enabling and starting etcd")
        subprocess.call(["systemctl", "enable", self._etcd_service])
        subprocess.call(["systemctl", "start", self._etcd_service])

    def is_active(self) -> bool:
        """Check if systemd etcd service is active."""
        try:
            cmd = f"systemctl is-active {self._etcd_service}"
            r = subprocess.check_output(shlex.split(cmd))
            return 'active' == r.decode().strip().lower()
        except subprocess.CalledProcessError as e:
            logger.error(f'## Could not check etcd: {e}')
            return False

    def configure(self):
        """Configure etcd instance."""
        # TODO set up password?
        # TODO set up port?
        # TODO enable metrics? Relate to prometheus?
        logger.debug("## configuring etcd")

    def set_list_of_accounted_nodes(self, nodes: List[str]) -> None:
        """Set list of nodes on etcd."""
        logger.debug(f"## setting on etcd: all_nodes/{nodes}")
        client = Etcd3Client(api_path="/v3/")
        client.put(key="all_nodes", value=json.dumps(nodes))
