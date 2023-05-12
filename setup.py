from setuptools import setup
import setuptools

install_deps = [
    "numpy>=1.20.1",
    "cellprofiler~=4.2.5",
    "cellprofiler-core~=4.2.5",
            ]

cellpose_deps = [
    "cellpose~=2.2"
]

omnipose_deps = [
    "omnipose"
]

stardist_deps = [
    "stardist"
]

    
setup(
    name="cellprofiler_plugins",
    packages=setuptools.find_packages(),
    install_requires = install_deps,
    extras_require = {
      "cellpose": cellpose_deps,
      "omnipose": omnipose_deps,
      "stardist": stardist_deps,
    }
)