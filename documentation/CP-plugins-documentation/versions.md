# Versions

The most current release can always be found on DockerHub at `cellprofiler/distributed-cellprofiler`.
Current version is 2.0.0.  
Our current tag system is dcpversion_CellProfilerversion, e.g. 1.2.0_3.1.8

Previous release versions can be accessed at `bethcimini/distributed-cellprofiler:versionnumber`

---

# Version History

## 2.1.0 (forthcoming)
* Increase support for using plugins
* Improve role handling and allow file download/upload from/to S3 buckets in different accounts
* Improve file download to S3FS can be completely bypassed
* Name EBS volumes

## 2.0.0rc2 - Released 20201110
* Add optional ability to download files to EBS rather than reading from S3 (helpful for pipelines that access many files/image sets)

## 2.0.0rc1 - Released 20201105

* Remove requirement for boto and fabric, using only boto3
* Add support for Python 3 and CellProfiler 4
* Move cluster size, machine type, and machine price to the config file from the fleet file, eliminating mismatches between the two
* Add the ability to filter only files with certain names when running CHECK_IF_DONE
* Don't cancel a fleet over capacity errors
* Add "cheapest" mode to the monitor, allowing you to run more cheaply (at possible expense of running more slowly)

## 1.2.2 - Released 20201103

* Allow pipelines using batch files to also designate an input output_top_directory
* Add support for multiple LaunchData specifications
* Add CellProfiler-plugins
* Additional way to create job submissions with run_batch_general.py

## 1.2.1 - Released 20200109, Updated through 20191002

* Allow monitor to downscale machines when number of jobs < number of machines
* Add a parameter to discount files when running CHECK_IF_DONE checks if less than a certain size

## 1.2.0 - Released 20181108, Updated through 20200109

* Improved compatibility with CellProfiler 2 and 3
* Better handling of logging when using output_structure

## 1.1.0 - Released 20170217, Updated 20170221 (bugfixes) - 20181018

* Changes in this release:

    * Added the `output_structure` variable to the job file, which allows you to structure the output folders created by DCP (ie `Plate/Well-Site` rather than `Plate-Well-Site`). Job files lacking this variable will still default to the previous settings (hyphenating all Metadata items in order they are presented in the Metadata grouping).  
    * Added support for creating the list of groups via `cellprofiler --print-groups`- see [this issue](https://github.com/CellProfiler/Distributed-CellProfiler/issues/52) for example and discussion.  Groups listed in this way MUST use the `output_structure` variable to state their desired folder structure or an error will be returned.

## 1.0.0 - Version as of 20170213
