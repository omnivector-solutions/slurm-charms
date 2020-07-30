#!/usr/bin/env python3
import logging
import os
import zipfile
import pathlib

logger = logging.getLogger(__name__)


class BuildCharm:
    def __init__(self):
        self.buildpath = pathlib.Path('/srv/build')

    def handle_package(self):
        """Handle the final package creation."""
        zipname = '/srv/out/slurmctld.charm'
        zipfh = zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED)
        buildpath_str = str(self.buildpath)  # os.walk does not support pathlib in 3.5
        for dirpath, dirnames, filenames in os.walk(buildpath_str, followlinks=True):
            dirpath = pathlib.Path(dirpath)
            for filename in filenames:
                filepath = dirpath / filename
                zipfh.write(str(filepath), str(filepath.relative_to(self.buildpath)))

        zipfh.close()
        return zipname

if __name__ == "__main__":
    charm = BuildCharm()
    print(charm.handle_package())
