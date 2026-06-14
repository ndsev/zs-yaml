"""Build for the optional zs_yaml_native loader extension.

rapidyaml is vendored under vendor/rapidyaml/ as the unmodified source tree of
the rapidyaml 0.15.0 PyPI sdist (MIT licensed). Built against the CPython
Limited API so one cp311-abi3 wheel per platform serves Python 3.11 and all
later versions.

Build in place for development:
  python setup.py build_ext --inplace
"""

import os
from glob import glob
from pathlib import Path
from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext

os.chdir(Path(__file__).parent.resolve())

LIMITED_API_VERSION_HEX = "0x030B0000"

RYML_SOURCES = sorted(
    glob("vendor/rapidyaml/src/c4/yml/*.cpp") + glob("vendor/rapidyaml/ext/c4core/src/c4/*.cpp")
)


class BuildExt(build_ext):
    """Pick compiler-appropriate C++17/optimization flags so the same source
    builds on Clang/GCC (-std=c++17) and MSVC (/std:c++17) for cibuildwheel."""

    def build_extensions(self):
        if self.compiler.compiler_type == "msvc":
            # /bigobj: rapidyaml's c4core translation units exceed the default
            # COFF section limit; /EHsc: standard C++ exception model.
            flags = ["/std:c++17", "/O2", "/EHsc", "/bigobj"]
        else:
            flags = ["-std=c++17", "-O3"]
        for ext in self.extensions:
            ext.extra_compile_args = flags
        super().build_extensions()


setup(
    name="zs_yaml_native",
    version="0.1",
    description="C-level rapidyaml-backed YAML loader for zs-yaml",
    cmdclass={"build_ext": BuildExt},
    ext_modules=[
        Extension(
            "zs_yaml_native",
            sources=["zs_yaml_native.cpp"] + RYML_SOURCES,
            include_dirs=["vendor/rapidyaml/src", "vendor/rapidyaml/ext/c4core/src"],
            py_limited_api=True,
            define_macros=[("Py_LIMITED_API", LIMITED_API_VERSION_HEX)],
        )
    ],
    options={"bdist_wheel": {"py_limited_api": "cp311"}},
    python_requires=">=3.11",
)
