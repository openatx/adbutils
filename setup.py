#!/usr/bin/env python
# coding: utf-8
#
# Licensed under MIT
#
# https://docs.travis-ci.com/user/deployment/pypi/

from __future__ import print_function

import setuptools
import subprocess
import sys

print("setup.py arguments:", sys.argv)

if sys.argv[-1] == "build_wheel":
    subprocess.call([sys.executable, "build_wheel.py"])
else:
    setuptools.setup(
        setup_requires=["pbr"],
        python_requires=">=3.8",
        pbr=True,
        package_data={"adbutils": ["py.typed"]},
        extras_require={
            "all": ["apkutils>=2.0.0,<3.0"],
        },
    )
