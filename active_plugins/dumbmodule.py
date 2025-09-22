#################################
#
# Imports from useful Python libraries
#
#################################

import locale
import sys

#################################
#
# Imports from CellProfiler
#
##################################

import cellprofiler_core.module
import cellprofiler_core.setting.text

__doc__ = """\
DumbModule
============

**DumbModule** does nothing of importance.


I am a module
look at me,
about as simple
as could be.

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
NO           NO            NO
============ ============ ===============

"""

#raise NotImplementedError("DumbModule does nothing")

class DumbModule(cellprofiler_core.module.Module):
    module_name = "DumbModule"
    category = "Info"

    variable_revision_number = 1

    def create_settings(self):
        self.some_setting = cellprofiler_core.setting.text.Text("dumb setting", "i am a setting", doc="I do nothing at all")

    def settings(self):
        return [self.some_setting]

    def visible_settings(self):
        return [self.some_setting]

    def run(self, workspace):
        f = open("/Users/ngogober/Desktop/log.txt", "wt")
        f_repr = repr(f)
        f.close()

        labels = ["func name", "value"]
        encoding_info_table = [
            ["locale.getdefaultlocale:", repr(locale.getdefaultlocale())],
            ["locale.getlocale", repr(locale.getlocale())],
            ["locale.getpreferredencoding (do not set)", repr(locale.getpreferredencoding(False))],
            ["locale.getpreferredencoding", repr(locale.getpreferredencoding())],
            ["sys.getfilesystemencoding", repr(sys.getfilesystemencoding())],
            ["filestream", f_repr],
        ]

        if self.show_window:
            workspace.display_data.statistics = encoding_info_table
            workspace.display_data.labels = labels
        else:
            print(encoding_info_table)

    def display(self, workspace, figure):
        statistics = workspace.display_data.statistics
        labels = workspace.display_data.labels
        figure.set_subplots((1, 1))
        figure.subplot_table(0, 0, statistics, labels)
