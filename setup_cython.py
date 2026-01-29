from setuptools import setup, Extension
from Cython.Build import cythonize
import numpy

extensions = [
    Extension(
        "consensus.powsolver.cpu_solver",
        ["consensus/powsolver/cpu_solver.pyx"],
        libraries=["crypto"], # Link against OpenSSL libcrypto
        # extra_compile_args=['-O3', '-march=native', '-ffast-math'],
        # extra_link_args=['-O3', '-march=native']
    )
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"}),
    script_args=["build_ext", "--inplace"]
)