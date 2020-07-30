#!/usr/bin/env python3
import logging
import os
import zipfile
import pathlib
import sys

logger = logging.getLogger(__name__)


class CharmZip:
    def __init__(self):
        self.buildpath = pathlib.Path(sys.argv[1])

    def handle_package(self):
        """Handle the final package creation."""
        zipname = f'out/{sys.argv[2]}.charm'
        zipfh = zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED)
        buildpath_str = str(self.buildpath)  # os.walk does not support pathlib in 3.5
        for dirpath, dirnames, filenames in os.walk(buildpath_str, followlinks=True):
            dirpath = pathlib.Path(dirpath)
            for filename in filenames:
                filepath = dirpath / filename
                zipfh.write(str(filepath), str(filepath.relative_to(self.buildpath)))

        zipfh.close()

if __name__ == "__main__":
    charm = CharmZip()
    charm.handle_package()
