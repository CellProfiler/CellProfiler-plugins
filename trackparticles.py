import numpy
import pandas
import trackpy

import cellprofiler.module
import cellprofiler.setting


class TrackParticles(cellprofiler.module.Module):
    category = "Object Processing"
    module_name = "TrackParticles"
    variable_revision_number = 1

    def is_aggregation_module(self):
        return True

    def create_settings(self):
        self.object_name = cellprofiler.setting.ObjectNameSubscriber(
            "Input object"
        )

        self.search_range = cellprofiler.setting.Integer(
            "Search range",
            value=5,
            minval=0
        )

        self.memory = cellprofiler.setting.Integer(
            "Memory",
            value=0,
            minval=0
        )

        self.neighbor_strategy = cellprofiler.setting.Choice(
            "Neighbor strategy",
            [
                "KDTree",
                "BTree"
            ]
        )

    def settings(self):
        return [
            self.object_name,
            self.search_range,
            self.memory,
            self.neighbor_strategy
        ]

    def run(self, workspace):
        pass

    def post_group(self, workspace, grouping):
        object_name = self.object_name.value
        measurements = workspace.measurements

        group_number = grouping["Group_Number"]
        groupings = measurements.get_groupings(grouping)
        image_numbers = sum([numbers for group, numbers in groupings if int(group["Group_Number"]) == group_number], [])

        # TODO: Optimize extracting:
        # Maybe it is faster to figure out how many objects there are and add values to a pre-initialized matrix.
        location_center_x = measurements.get_measurement(object_name, "Location_Center_X", image_numbers)
        location_center_y = measurements.get_measurement(object_name, "Location_Center_Y", image_numbers)
        frame = [[i] * len(loc) for i, loc in enumerate(location_center_x)]

        location_center_x = numpy.concatenate(location_center_x)
        location_center_y = numpy.concatenate(location_center_y)
        frame = sum(frame, [])

        frame_info = pandas.DataFrame({
            "x": location_center_x,
            "y": location_center_y,
            "frame": frame
        })


        trajectories = trackpy.link_df(
            f=frame_info,
            search_range=self.search_range.value,
            memory=self.memory.value,
            neighbor_strategy=self.neighbor_strategy.value
        )

        # TODO: Figure out what measurements to store. Look at TrackObjects as an example.

        if self.show_window:
            workspace.display_data.trajectories = trajectories.values

    def display_post_group(self, workspace, figure):
        if self.show_window:
            figure.set_subplots((1, 1))
            # convert trajectories to a data frame
            trajectories = pandas.DataFrame(workspace.display_data.trajectories,
                                            columns=["frame", "x", "y", "particle"])
            ax = trackpy.plot_traj(trajectories)
            figure.subplots[0, 0] = ax
