#!/usr/bin/env python
# coding: utf-8
#
# Licensed under MIT
#

from __future__ import print_function

import setuptools
# import sys

# if sys.version_info < (3, 6):
#     error = """
# Error: adbutils only support Python 3.6 and above.

# Python {py} detected.
# """.format(py=sys.version_info)

#     print(error, file=sys.stderr)
#     sys.exit(1)

setuptools.setup(
    setup_requires=['pbr'],
    python_requires='>=2.7',
    pbr=True,
    py_modules=["adbutils"])
