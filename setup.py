import setuptools
from setuptools import setup

install_deps = [
    "cellprofiler",
    "cellprofiler-core",
]

cellpose_deps = [
    "cellpose>=1.0.2"
]

omnipose_deps = [
    "omnipose",
    "ncolor"
]

stardist_deps = [
    "tensorflow",
    "stardist"
]

imagejscript_deps = [
    "pyimagej"
]

# The zeroc-ice version OMERO needs is very difficult to build, so here are some premade wheels for a bunch of platforms
omero_deps = [
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-macos-x86_64/releases/download/20220722/zeroc_ice-3.6.5-cp310-cp310-macosx_10_15_x86_64.whl ; sys_platform == 'darwin' and python_version == '3.10'",
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-macos-x86_64/releases/download/20220722/zeroc_ice-3.6.5-cp39-cp39-macosx_10_15_x86_64.whl ; sys_platform == 'darwin' and python_version == '3.9'",
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-macos-x86_64/releases/download/20220722/zeroc_ice-3.6.5-cp38-cp38-macosx_10_15_x86_64.whl ; sys_platform == 'darwin' and python_version == '3.8'",
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-ubuntu2204-x86_64/releases/download/20221004/zeroc_ice-3.6.5-cp310-cp310-linux_x86_64.whl ; 'Ubuntu' in platform_version and python_version == '3.10'",
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20221003/zeroc_ice-3.6.5-cp310-cp310-manylinux_2_17_x86_64.manylinux2014_x86_64.whl ; sys_platform == 'linux' and python_version == '3.10' and 'Ubuntu' not in platform_version",
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20221003/zeroc_ice-3.6.5-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl ; sys_platform == 'linux' and python_version == '3.9'",
    "zeroc-ice @ https://github.com/glencoesoftware/zeroc-ice-py-linux-x86_64/releases/download/20221003/zeroc_ice-3.6.5-cp38-cp38-manylinux_2_17_x86_64.manylinux2014_x86_64.whl ; sys_platform == 'linux' and python_version == '3.8'",
    "omero-py",
    "omero-user-token",
]

setup(
    name="cellprofiler_plugins",
    packages=setuptools.find_packages(),
    install_requires=install_deps,
    extras_require={
        "cellpose": cellpose_deps,
        "omnipose": omnipose_deps,
        "stardist": stardist_deps,
        "imagejscript": imagejscript_deps,
        "omero": omero_deps,
    },
)
