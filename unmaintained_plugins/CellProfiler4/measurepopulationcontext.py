'''<b>MeasurePopulationContext</b> - a module implementing cell density and distance
   from edge.

   The module makes two measurements: <br><ul>
   <li><b>PopContext_Count</b> - the number of neighbors within the given radius</li>
   <li><b>PopContext_Density</b>, a calcuation of
   Ripley's K function (Ripley, <i>Modelling Spatial Patterns</i>,
   Journal of the Royal Statistical Society, Series B 39, 172-192.). This is
   a normalized measure of the density of object centers within a given radius.
   Here, we implement the normalized version which takes edge effects into
   account (a cell near the edge of the image will not have neighbors beyond
   the edge of the image, so we normalize by the portion of the circle
   with the given radius that is outside of the image, padded by the typical
   radius of a cell). The K function values are fairly large because the values
   are proportional to the square of the radius. The Ripley L function is
   (K/pi)<sup>1/2</sup> and is proportional to the radius.
   </li>
   <li><b>PopContext_Edge</b>, a measure of the distance of an object from
   the edge of the foreground of a binary image.</li>
'''
# CellProfiler is distributed under the GNU General Public License.
# See the accompanying file LICENSE for details.
#
# Copyright (c) 2003-2009 Massachusetts Institute of Technology
# Copyright (c) 2009-2012 Broad Institute
#
# Please see the AUTHORS file for credits.
#
# Website: http://www.cellprofiler.org

import numpy as np
from cellprofiler_core.constants.measurement import M_LOCATION_CENTER_X, M_LOCATION_CENTER_Y, COLTYPE_FLOAT, \
    COLTYPE_INTEGER
from cellprofiler_core.setting.choice import Choice
from cellprofiler_core.setting.subscriber import LabelSubscriber, ImageSubscriber
from cellprofiler_core.setting.text import Integer
from scipy.ndimage import distance_transform_edt, gaussian_filter
from scipy.ndimage import binary_erosion, binary_dilation

import cellprofiler_core.module as cpm
import cellprofiler_core.preferences as cpprefs
import matplotlib.cm

O_POPULATION_DENSITY = "Population density"
O_DISTANCE_TO_EDGE = "Distance to edge"
O_BOTH = "Both"

C_POP_CONTEXT = "PopContext"
FTR_DENSITY = "Density"
FTR_COUNT = "Count"
FTR_EDGE = "Edge"

M_DENSITY_FMT = "_".join((C_POP_CONTEXT, FTR_DENSITY, "%d"))
M_COUNT_FMT = "_".join((C_POP_CONTEXT, FTR_COUNT, "%d"))
M_EDGE_FMT = "_".join((C_POP_CONTEXT, FTR_EDGE, "%s"))

class MeasurePopulationContext(cpm.Module):
    module_name = "MeasurePopulationContext"
    category = 'Measurement'
    variable_revision_number = 1

    def create_settings(self):
        self.object_name = LabelSubscriber(
            "Input objects", "None",
            doc = """Enter the name of the objects whose population context is
            to be measured.""")
        self.operation = Choice(
            "Operation",
            choices= (O_POPULATION_DENSITY, O_DISTANCE_TO_EDGE, O_BOTH),
            doc = """Select the measurements you wish to perform. The choices
            are:<br><ul>
            <li><i>%(O_POPULATION_DENSITY)s</i> - calculate the population
            density within a radius from each cell.</li>
            <li><i>%(O_DISTANCE_TO_EDGE)s</i> - calculate the distance of
            each cell from the edge of a binary mask.</li>
            <li><i>%(O_BOTH)s</i> - make both measurements"""%globals())
        self.radius = Integer(
            "Search radius", 50, minval=1,
            doc = """Count all objects within this radius""")
        self.object_diameter = Integer(
            "Object diameter", 20, minval=0,
            doc = """The average diameter of objects in the image. This number
            is used to adjust the area of the image to account for objects
            that would otherwise be excluded because they were touching
            the border.""")
        self.edge_image = ImageSubscriber(
            "Edge image",
            doc = """For measuring distance to an edge, this is the reference
            image. Cell distances will be computed to the nearest foreground / 
            background edge in the reference image.""")

    def settings(self):
        return [self.object_name, self.operation, self.radius,
                self.object_diameter, self.edge_image]

    def visible_settings(self):
        result = [self.object_name, self.operation]
        if self.wants_population_density():
            result += [self.radius, self.object_diameter]
        if self.wants_distance_to_edge():
            result.append(self.edge_image)

        return result

    def wants_population_density(self):
        return self.operation.value in [O_POPULATION_DENSITY, O_BOTH]

    def wants_distance_to_edge(self):
        return self.operation.value in [O_DISTANCE_TO_EDGE, O_BOTH]

    def density_feature(self):
        return M_DENSITY_FMT % self.radius.value

    def count_feature(self):
        return M_COUNT_FMT % self.radius.value

    def edge_feature(self):
        return M_EDGE_FMT % self.edge_image.value

    def is_interactive(self):
        return False

    def run(self, workspace):
        if self.wants_population_density():
            self.calculate_population_density(workspace)
        if self.wants_distance_to_edge():
            self.calculate_distance_to_edge(workspace)

    def calculate_population_density(self, workspace):
        m = workspace.measurements
        j, i = [m.get_current_measurement(self.object_name.value, f)
                for f in (M_LOCATION_CENTER_X, M_LOCATION_CENTER_Y)]
        objects = workspace.object_set.get_objects(self.object_name.value)
        shape = np.array(objects.shape, float)
        object_diameter = float(self.object_diameter.value)
        object_radius = object_diameter / 2
        radius = float(self.radius.value)
        #
        # Lambda is a measure of the density of cell count / area. Objects
        # touching the edge force us to exclude the area of the image
        # from 0 to 1/2 of the diameter and from 1/2 of the diameter to
        # the edge of the image.
        #
        l = float(len(j)) / float(np.prod(shape-object_diameter))
        #
        # We need to account for the portion of the circle that might be
        # outside of the image, for objects on the end. We map the i of all
        # centers closest to the far side to shape[0] - i and similarly
        # for j so we just can deal with how close i and j are to 0.
        #
        # We then measure the area of the shape formed by the circle intersected
        # by the line at object_radius. If an object is in the corner, we
        # have doubly subtracted for it - TBD fix it.
        #
        ii, jj = i.copy(), j.copy()
        half_shape = shape / 2
        ii[ii > half_shape[0]] = shape[0] - ii
        jj[jj > half_shape[1]] = shape[1] - jj

        atotal = np.pi * radius * radius
        a = atotal * np.ones(len(ii), float)
        ii_close = ii < (radius + object_radius)
        chord_angle = 2 * np.arccos((ii[ii_close] - object_radius) / radius)
        chord_area = radius * radius *( chord_angle - np.sin(chord_angle)) / 2
        a[ii_close] -= chord_area
        jj_close = jj < (radius + object_radius)
        chord_angle = 2 * np.arccos((jj[jj_close] - object_radius) / radius)
        chord_area = radius * radius *( chord_angle - np.sin(chord_angle)) / 2
        a[jj_close] -= chord_area

        adj = a / atotal

        di = ii[:, np.newaxis] - ii[np.newaxis, :]
        dj = jj[:, np.newaxis] - jj[np.newaxis, :]
        d2 = di * di + dj * dj
        #
        # Count # within the radius including ourself
        #
        density_counts = np.sum(d2 <= radius * radius, 0)
        #
        # Count of neighbors
        #
        counts = density_counts -1
        #
        k = 1/ l * adj * counts
        m.add_measurement(self.object_name.value,
                          self.count_feature(),
                          counts)
        m.add_measurement(self.object_name.value,
                          self.density_feature(),
                          k)
        if workspace.frame is not None:
            display = workspace.display_data.count_display = -np.ones(objects.shape, int)
            for labels, indices in objects.get_labels():
                display[labels != 0] = counts[labels[labels!=0]-1]

    def calculate_distance_to_edge(self, workspace):
        m = workspace.measurements
        edge = workspace.image_set.get_image(self.edge_image.value,
                                             must_be_binary=True)
        edge = edge.pixel_data
        objects = workspace.object_set.get_objects(self.object_name.value)
        distance = np.ones(objects.count) * np.sqrt(np.prod(edge.shape)) / 2
        for e in (edge, ~edge):
            d = distance_transform_edt(e)
            for labels, indices in objects.get_labels():
                #
                # A mask of labeled points outside of the edge object
                #
                mask = (labels != 0) & (d != 0)
                dm = d[mask]
                lm = labels[mask]
                #
                # Order by distance, then label, take the first of
                # each label to find the minimum
                #
                order = np.lexsort((dm, lm))
                lm, dm = lm[order], dm[order]
                smallest = np.hstack([[True], lm[:-1] != lm[1:]])
                distance[lm[smallest]-1] = \
                    np.minimum(dm[smallest], distance[lm[smallest]-1])
        m.add_measurement(self.object_name.value,
                          self.edge_feature(),
                          distance)
        if workspace.frame is not None:
            dpicture = workspace.display_data.distances = -np.ones(edge.shape)
            for labels, indices in objects.get_labels():
                dpicture[labels!=0] = distance[labels[labels!=0] - 1]
            workspace.display_data.edge = (
                binary_dilation(edge, structure=np.ones((3,3), bool)) !=
                binary_erosion(edge, structure=np.ones((3,3), bool), border_value=1))

    def display(self, workspace, figure):
        import matplotlib
        nsubplots = 0
        if self.wants_population_density():
            nsubplots += 1
        if self.wants_distance_to_edge():
            nsubplots += 1
        figure = workspace.create_or_find_figure(subplots=(nsubplots, 1))
        cmap = cpprefs.get_default_colormap()
        cm = matplotlib.cm.get_cmap(cmap)
        cm.set_bad(color='black')
        axes = None
        if self.wants_population_density():
            image = np.ma.MaskedArray(workspace.display_data.count_display,
                                      workspace.display_data.count_display < 0)
            title = "# objects within %d px" % self.radius.value
            axes = figure.subplot_imshow(0, 0, image, title = title,
                                         colormap = cm, colorbar=True,
                                         normalize = False,
                                         vmin = 0,
                                         vmax = np.max(image))
        if self.wants_distance_to_edge():
            sm = matplotlib.cm.ScalarMappable(cmap = cm)
            image = np.ma.MaskedArray(workspace.display_data.distances,
                                      workspace.display_data.distances < 0)
            image = sm.to_rgba(image)
            #
            # We give the edge a little blur so that single pixels show up ok
            #
            edge = gaussian_filter(workspace.display_data.edge.astype(float), 3)
            edge = edge / np.max(edge)
            edge_color = sm.to_rgba(np.array([np.max(workspace.display_data.distances)]))[0]
            image = image * (1 - edge[:, :, np.newaxis]) + \
                edge[:, :, np.newaxis] * edge_color[np.newaxis, np.newaxis, :]
            figure.subplot_imshow(nsubplots-1, 0, image,
                                  title = "Distance to edge")


    def get_measurement_columns(self, pipeline):
        result = []
        if self.wants_population_density():
            result += [(self.object_name.value,
                        self.density_feature(),
                        COLTYPE_FLOAT),
                       (self.object_name.value,
                        self.count_feature(),
                        COLTYPE_INTEGER)]
        if self.wants_distance_to_edge():
            result += [(self.object_name.value,
                        self.edge_feature(),
                        COLTYPE_FLOAT)]
        return result

    def get_categories(self, pipeline, object_name):
        if object_name == self.object_name:
            return [C_POP_CONTEXT]
        return []

    def get_measurements(self, pipeline, object_name, category):
        result = []
        if category not in self.get_categories(pipeline, object_name):
            return result
        if self.wants_population_density():
            result += [FTR_DENSITY, FTR_COUNT]
        if self.wants_distance_to_edge():
            result += [FTR_EDGE]
        return result

    def get_measurement_images(self, pipeline, object_name, category, measurement):
        if category not in self.get_categories(pipeline, object_name):
            return []
        if not self.wants_distance_to_edge():
            return []
        if measurement != FTR_EDGE:
            return []
        return [self.edge_image.value]

    def get_measurement_scales(self, pipeline, object_name, category,
                               measurement, image_name):
        if category not in self.get_categories(pipeline, object_name):
            return []
        if not self.wants_population_density():
            return []
        if measurement not in (FTR_COUNT, FTR_DENSITY):
            return []
        return [self.radius.value]
