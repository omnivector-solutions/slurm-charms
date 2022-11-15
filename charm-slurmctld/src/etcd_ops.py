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

from jinja2 import Environment, FileSystemLoader
from slurm_ops_manager.utils import operating_system

from omnietcd3 import Etcd3AuthClient

logger = logging.getLogger()


class EtcdOps:
    """ETCD ops."""

    def __init__(self, charm):
        """Initialize class."""
        self._charm = charm

        # system user and group
        self._etcd_user = "etcd"
        self._etcd_group = "etcd"
        self._etcd_service = "etcd.service"

        if operating_system() == 'ubuntu':
            self._etcd_environment_file = Path("/etc/default/etcd")
        else:
            self._etcd_environment_file = Path("/etc/sysconfig/etcd")

        self._certs_path = Path("/var/lib/etcd/tls_certificates/")
        self._tls_key_path = self._certs_path / "tls.key"
        self._tls_crt_path = self._certs_path / "tls.crt"
        self._tls_ca_crt_path = self._certs_path / "tls-ca.crt"

    def install(self, resource_path: Path):
        """Install etcd."""
        # extract resource tarball
        with TemporaryDirectory(prefix="omni") as tmp_dir:
            logger.debug(f"## extracting {resource_path} to {tmp_dir}")
            with tarfile.open(resource_path, 'r') as tar:
                
                import os
                
                def is_within_directory(directory, target):
                    
                    abs_directory = os.path.abspath(directory)
                    abs_target = os.path.abspath(target)
                
                    prefix = os.path.commonprefix([abs_directory, abs_target])
                    
                    return prefix == abs_directory
                
                def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
                
                    for member in tar.getmembers():
                        member_path = os.path.join(path, member.name)
                        if not is_within_directory(path, member_path):
                            raise Exception("Attempted Path Traversal in Tar File")
                
                    tar.extractall(path, members, numeric_owner=numeric_owner) 
                    
                
                safe_extract(tar, path=tmp_dir)

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

        template_dir = Path(__file__).parent / "templates"
        environment = Environment(loader=FileSystemLoader(template_dir))

        # service unit
        template = environment.get_template("etcd.service.tmpl")
        ctxt = {"environment_file": self._etcd_environment_file}
        dest = Path("/etc/systemd/system/") / self._etcd_service
        dest.write_text(template.render(ctxt))

        subprocess.call(["systemctl", "daemon-reload"])

    def _setup_environment_file(self):
        logger.debug("## creating environemnt file for etcd")
        template_dir = Path(__file__).parent / "templates"
        environment = Environment(loader=FileSystemLoader(template_dir))

        template = environment.get_template("etcd.env.tmpl")

        if self._charm._stored.use_tls:
            ctxt = {"use_tls": True,
                    "protocol": "https",
                    "tls_key_path": self._tls_key_path,
                    "tls_cert_path": self._tls_crt_path,
                    }
            if self._charm._stored.use_tls_ca:
                ctxt["ca_cert_path"] = self._tls_ca_crt_path
        else:
            ctxt = {"use_tls": False,
                    "protocol": "http"}

        self._etcd_environment_file.write_text(template.render(ctxt))

    def setup_tls(self):
        """Setup the files for TLS."""
        logger.debug("## setting tls files for etcd")

        # safeguard
        if not self._charm._stored.use_tls:
            logger.debug("## no certificates provided")
            # must restart if user removed certs
            self._setup_environment_file()
            self.restart()
            return

        # create dir to store certs
        if not self._certs_path.exists():
            logger.debug("## creating directory to store certs")
            self._certs_path.mkdir(parents=True)

        # create the files
        logger.debug("## creating cert files")
        key = self._charm.model.config["tls-key"]
        self._tls_key_path.write_text(key)
        crt = self._charm.model.config["tls-cert"]
        self._tls_crt_path.write_text(crt)

        ca_crt = self._charm.model.config["tls-ca-cert"]
        if ca_crt:
            logger.debug("## creating ca cert file")
            self._tls_ca_crt_path.write_text(ca_crt)

        # set correct permissions
        shutil.chown(self._certs_path, user=self._etcd_user, group=self._etcd_group)
        self._certs_path.chmod(0o500)

        # update configurations and restart
        self._setup_environment_file()
        self.restart()

    def stop(self):
        """Stop etcd service."""
        logger.debug("## stopping etcd")
        subprocess.call(["systemctl", "stop", self._etcd_service])

    def start(self):
        """Start etcd service."""
        logger.debug("## enabling and starting etcd")
        subprocess.call(["systemctl", "enable", self._etcd_service])
        subprocess.call(["systemctl", "start", self._etcd_service])

    def restart(self):
        """Restart etcd service."""
        logger.debug("## restarting etcd")
        subprocess.call(["systemctl", "restart", self._etcd_service])

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
        """Configure etcd service for the first time."""
        logger.debug("## configuring etcd")

        # rewrite environment file and start service
        self.setup_tls()
        self._setup_environment_file()
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
        cmds = [# create root account
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

    def _client(self, root_pass: str) -> Etcd3AuthClient:
        """Build an etcd client with the correct protocol.

        Use https if we have TLS certs and HTTP otherwise.
        """
        protocol = "http"
        tls_cert = None
        cacert = None

        if self._charm._stored.use_tls:
            protocol = "https"
            tls_cert = self._tls_crt_path.as_posix()

            if self._charm._stored.use_tls_ca:
                cacert = self._tls_ca_crt_path.as_posix()
        logger.debug(f"## Created new etcd client using {protocol}, {tls_cert} and {cacert}")
        client = Etcd3AuthClient(username="root", password=root_pass,
                                 protocol=protocol, ca_cert=cacert,
                                 cert_cert=tls_cert)
        client.authenticate()
        return client

    def set_list_of_accounted_nodes(self, root_pass: str, nodes: List[str]) -> None:
        """Set list of nodes on etcd."""
        logger.debug(f"## setting on etcd: nodes/all_nodes/{nodes}")
        client = self._client(root_pass)
        client.put(key="nodes/all_nodes", value=json.dumps(nodes))

    def store_munge_key(self, root_pass: str, key: str) -> None:
        """Store munge key on etcd."""
        logger.debug("## Storing munge key on etcd: munge/key")
        client = self._client(root_pass)
        client.put(key="munge/key", value=key)
