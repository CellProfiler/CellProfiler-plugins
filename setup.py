from setuptools import setup
import setuptools

if __name__!="__main__":
    print("Please change your plugins folder to the 'active plugins' subfolder")

else:
    install_deps = [
        "cellprofiler",
        "cellprofiler-core",
                ]

    cellpose_deps = [
        "cellpose>=1.0.2,<3.0"
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

    setup(
        name="cellprofiler_plugins",
        packages=setuptools.find_packages(),
        install_requires = install_deps,
        extras_require = {
          "cellpose": cellpose_deps,
          "omnipose": omnipose_deps,
          "stardist": stardist_deps,
          "imagejscript": imagejscript_deps,
        }
    )
