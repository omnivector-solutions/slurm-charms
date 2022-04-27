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

from omnietcd3 import Etcd3AuthClient

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

    def configure(self, root_pass: str, slurmd_pass: str) -> None:
        """Configure etcd service."""
        logger.debug("## configuring etcd")
        self.start()

        # some configs can only be applied with the server running
        self.setup_default_roles(root_pass=root_pass, slurmd_pass=slurmd_pass)

    def setup_default_roles(self, root_pass: str, slurmd_pass: str) -> None:
        """Set up default etcd roles.

        We use three roles:
        - root: for slurmctld operations
            - has full r/w permissions
        - slurmd: for slurmd charms
            - has r/w permissions only for nodes/* keys
        - munge: for external accounts reading the munge key
            - has r permissions for munge/* keys
        """
        logger.debug("## creating default etcd roles/users")
        cmds = [# create root account with random pass
                f"etcdctl user add root:{root_pass}",
                # create root role
                "etcdctl role add root",
                "etcdctl user grant-role root root",

                # create slurmd user
                f"etcdctl user add slurmd:{slurmd_pass}",
                # create slurmd role
                "etcdctl role add slurmd",
                "etcdctl role grant-permission slurmd readwrite --prefix=true nodes/",
                # grant slurmd user the slurmd role
                "etcdctl user grant-role slurmd slurmd",

                # create munge role
                "etcdctl role add munge-readers",
                "etcdctl role grant-permission munge-readers read --prefix=true munge/",

                # enable auth
                "etcdctl auth enable",
               ]

        for cmd in cmds:
            cmd_without_password = cmd.split(":")[0]
            logger.debug(f"## executing command: {cmd_without_password}")
            subprocess.run(shlex.split(cmd))

    def create_new_munge_user(self, root_pass: str, user: str, password: str) -> None:
        """Create new user in etcd with munge-readers role."""
        logger.debug("## creating new account to query munge key")
        auth = f"--user root --password {root_pass}"

        cmd = f"etcdctl {auth} user add {user}:{password}"
        subprocess.run(shlex.split(cmd))

        logger.debug("## granting role munge-readers to new account")
        cmd = f"etcdctl {auth} user grant-role {user} munge-readers"
        subprocess.run(shlex.split(cmd))

    def set_list_of_accounted_nodes(self, root_pass: str, nodes: List[str]) -> None:
        """Set list of nodes on etcd."""
        logger.debug(f"## setting on etcd: nodes/all_nodes/{nodes}")
        client = Etcd3AuthClient(username="root", password=root_pass)
        client.put(key="nodes/all_nodes", value=json.dumps(nodes))

    def store_munge_key(self, root_pass: str, key: str) -> None:
        """Store munge key on etcd."""
        logger.debug("## Storing munge key on etcd: munge/key")
        client = Etcd3AuthClient(username="root", password=root_pass)
        client.put(key="munge/key", value=key)
