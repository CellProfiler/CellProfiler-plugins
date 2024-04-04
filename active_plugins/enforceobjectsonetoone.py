import numpy

import cellprofiler_core.object
from cellprofiler_core.constants.measurement import (
    C_PARENT,
    C_CHILDREN,
    C_COUNT,
    C_LOCATION,
    C_NUMBER,
    FTR_CENTER_X,
    FTR_CENTER_Y,
    FTR_CENTER_Z,
    FTR_OBJECT_NUMBER,
)
from cellprofiler_core.module.image_segmentation import ObjectProcessing
from cellprofiler_core.setting.subscriber import LabelSubscriber
from cellprofiler_core.setting.text import LabelName

from cellprofiler.modules import _help

__doc__ = """\
EnforceObjectsOneToOne
======================

**EnforceObjectsOneToOne** takes two sets of objects which were independently 
generated (often, though need not be, by a deep learning plugin) and forces
the object sets to create a 1-to-1 object relationship that matches what happens
in IdentifyPrimaryObjects and IdentifySecondaryObjects. Pseudo-primary objects
are also forced to not go outside the pseudo-secondary object.

TODO - describe heuristic, tie handling

|

============ ============ ===============
Supports 2D? Supports 3D? Respects masks?
============ ============ ===============
YES          YES          YES
============ ============ ===============

See also
^^^^^^^^

See also: **RelateObjects**

{HELP_ON_SAVING_OBJECTS}

Measurements made by this module
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

""".format(
    **{"HELP_ON_SAVING_OBJECTS": _help.HELP_ON_SAVING_OBJECTS}
)


class EnforceObjectsOneToOne(ObjectProcessing):
    module_name = "EnforceObjectsOneToOne"

    variable_revision_number = 1

    def create_settings(self):
        super(EnforceObjectsOneToOne, self).create_settings()

        self.x_name.text = "Pre-primary objects"

        self.x_name.doc = """\
TODO
        """

        self.y_name = LabelSubscriber(
            "Pre-secondary objects",
            doc="""\
TODO
            """,
        )

        self.output_primary_objects_name = LabelName(
            "Name the output primary object",
            "PrimaryObjects",
            doc="""\
TODO """,
        )

        self.output_secondary_objects_name = LabelName(
            "Name the output secondary object",
            "SecondaryObjects",
            doc="""\
TODO """,
        )


    def settings(self):

        settings = super(EnforceObjectsOneToOne, self).settings()

        settings += [
            self.output_primary_objects_name,
            self.output_secondary_objects_name
        ]
        return settings

    def visible_settings(self):
        visible_settings = super(EnforceObjectsOneToOne, self).visible_settings()

        visible_settings += [
            self.output_primary_objects_name,
            self.output_secondary_objects_name
        ]

        return visible_settings

    def run(self, workspace):
        pre_primary = workspace.object_set.get_objects(self.x_name.value)

        pre_primary_seg = pre_primary.segmented

        pre_secondary = workspace.object_set.get_objects(self.y_name.value)

        pre_secondary_seg = pre_secondary.segmented

        primary_seg = self.enforce_unique(pre_primary_seg, pre_secondary_seg, erode_excess=True)

        secondary_seg = self.enforce_unique(pre_secondary_seg, primary_seg)

        new_primary_objects = cellprofiler_core.object.Objects()
        new_primary_objects.segmented = primary_seg
        if pre_primary.has_parent_image:
            new_primary_objects.parent_image = pre_primary.parent_image
        #we are NOT handling ie unedited segmented, since those are rarely made in DL

        new_secondary_objects = cellprofiler_core.object.Objects()
        new_secondary_objects.segmented = secondary_seg
        if pre_secondary.has_parent_image:
            new_secondary_objects.parent_image = pre_secondary.parent_image
        #we are NOT handling ie unedited segmented, since those are rarely made in DL

        workspace.object_set.add_objects(new_primary_objects, self.output_primary_objects_name.value)

        workspace.object_set.add_objects(new_secondary_objects, self.output_secondary_objects_name.value)

        #relate new primary to new secondary, and get the measurements
        self.add_measurements(workspace,self.x_name.value, self.output_primary_objects_name.value)

        #relate old primary to new primary, and get the measurements
        self.add_measurements(workspace,self.y_name.value, self.output_secondary_objects_name.value)

        #relate old secondary to new secondary, and get the measurements
        self.add_measurements(workspace,self.output_primary_objects_name.value, self.output_secondary_objects_name.value)

        if self.show_window:
            #isdone? NO
            """workspace.display_data.parent_labels = pre_primary.segmented

            workspace.display_data.parent_count = parents.count

            workspace.display_data.child_labels = children.segmented

            workspace.display_data.parents_of = parents_of

            workspace.display_data.dimensions = parents.dimensions"""

    def display(self, workspace, figure):
        #isdone? NO
        return 
        if not self.show_window:
            return

        dimensions = workspace.display_data.dimensions

        figure.set_subplots((1, 3), dimensions=dimensions)

        """child_labels = workspace.display_data.child_labels

        parents_of = workspace.display_data.parents_of

        parent_labels = workspace.display_data.parent_labels

        #
        # discover the mapping so that we can apply it to the children
        #
        mapping = numpy.arange(workspace.display_data.parent_count + 1)

        mapping[parent_labels] = parent_labels

        parent_labeled_children = numpy.zeros(child_labels.shape, int)

        mask = child_labels > 0

        parent_labeled_children[mask] = mapping[parents_of[child_labels[mask] - 1]]

        max_label = max(
            parent_labels.max(), child_labels.max(), parent_labeled_children.max()
        )

        seed = numpy.random.randint(256)

        cmap = figure.return_cmap(max_label)

        figure.subplot_imshow_labels(
            0,
            0,
            parent_labels,
            title=self.x_name.value,
            max_label=max_label,
            seed=seed,
            colormap=cmap,
        )

        figure.subplot_imshow_labels(
            1,
            0,
            child_labels,
            title=self.y_name.value,
            sharexy=figure.subplot(0, 0),
            max_label=max_label,
            seed=seed,
            colormap=cmap,
        )

        figure.subplot_imshow_labels(
            0,
            1,
            parent_labeled_children,
            title="{} labeled by {}".format(self.y_name.value, self.x_name.value),
            sharexy=figure.subplot(0, 0),
            max_label=max_label,
            seed=seed,
            colormap=cmap,
        )"""

    def enforce_unique(self, primary_object_array,secondary_object_array,erode_excess=False):
        hist, _, _ = numpy.histogram2d(
            primary_object_array.flatten(),
            secondary_object_array.flatten(),
            bins=[range(primary_object_array.max()+2),range(secondary_object_array.max()+2)]
        )
        sanity_check_list = []
        # for each nucleus
        primary_copy = primary_object_array.copy()
        for primary in numpy.unique(primary_object_array)[1:]:
            secondary_in_primary = hist[primary,:]
            # if I don't touch any cells, nothing to do
            if secondary_in_primary[1:].sum() == 0 :
                secondary_match = 0
            # if do I touch any cells
            else:
                # default assumption: I never find a cell buddy :( . Keeps us from having to write a bunch of else's that explicitly set this
                secondary_match = 0
                # what cells do I touch
                secondaries_touched = list(secondary_in_primary[1:].nonzero()[0]+1)
                
                # let's figure out how much I touch them, with a lot of annoying complexity to account for ties
                overlap_dict = {}
                for each_secondary in secondaries_touched:
                    overlap = hist[primary,each_secondary]
                    if overlap not in overlap_dict.keys():
                        overlap_dict[overlap]=[each_secondary]
                    else:
                        overlap_dict[overlap].append(each_secondary)
                areas = list(overlap_dict.keys())
                areas.sort(reverse=True)
                order_to_try = []
                for each_area in areas:
                    order_to_try+=overlap_dict[each_area]

                # now starting from the cell I touch the most, let's see if I am the best nucleus. Break if I ever am
                for each_secondary in order_to_try:
                    # what other nuclei touch this cell
                    secondary_touchers = hist[1:,each_secondary].nonzero()[0]+1
                    #if the cell I touch most only touches me:
                    if secondary_touchers.shape == 1:
                        secondary_match = each_secondary
                        break
                    # if it's more than just me:
                    else:
                        # if multiple nuclei pick the same cell, pick the nucleus with the best percent overlap
                        best_primary_score = 0
                        best_primary = []
                        for each_toucher in secondary_touchers:
                            score = hist[each_toucher,each_secondary]/hist[each_toucher,1:].sum()
                            if score > best_primary_score:
                                best_primary_score = score
                                best_primary = [each_toucher]
                            elif score == best_primary_score:
                                best_primary.append([each_toucher])
                        # do I win?
                        if best_primary == [primary]:
                            secondary_match = each_secondary
                            break
                        # do I at least tie - if so, pick the nucleus with the most inside the cell
                        elif primary in best_primary:
                            best_tiebreaker_score = 0
                            best_tiebreaker = []
                            for each_primary in best_primary:
                                if hist[each_primary,each_secondary] > best_tiebreaker_score:
                                    best_tiebreaker_score = hist[each_primary,each_secondary]
                                    best_tiebreaker = [each_primary]
                                elif hist[each_primary,each_secondary] == best_tiebreaker_score:
                                    best_tiebreaker.append(each_primary)
                                # do I win outright? If a tie, everyone loses (because otherwise 1:1 might die)
                                if best_tiebreaker == [primary]:
                                    # I win - otherwise, the default secondary_match of 0 still applies
                                    secondary_match = each_secondary
            if secondary_match != 0:
                sanity_check_list.append(secondary_match)
                if erode_excess:
                    primary_copy = numpy.where((primary_object_array == primary) & (secondary_object_array != secondary_match), 0, primary_copy)
            else:
                primary_copy = numpy.where(primary_object_array == primary, 0, primary_copy)

        # One last sanity check - are we ever linking two different primaries to the same secondary?
        _, matched_to_count = numpy.unique(numpy.array(sanity_check_list),return_counts = True)
        if matched_to_count.max() >1:
            raise RuntimeError(f"Maximum time any secondary object was matched to: {matched_to_count.max()}.")
        
        # reindex the labels to be consecutive
        # mostly stolen from RelateObjects, which says it's mostly stolen from FilterObjects
        indexes = numpy.unique(primary_copy)[1:]
        # Create an array that maps label indexes to their new values
        # All labels to be deleted have a value in this array of zero
        new_object_count = len(indexes)
        max_label = numpy.max(primary_copy)
        label_indexes = numpy.zeros((max_label + 1,), int)
        label_indexes[indexes] = numpy.arange(1, new_object_count + 1)

        #
        # Reindex the labels of the old source image
        #
        primary_copy[primary_copy > max_label] = 0
        primary_copy = label_indexes[primary_copy]    
    
        return primary_copy

    def get_measurement_columns(self, pipeline):
         return super(EnforceObjectsOneToOne, self).get_measurement_columns(
            pipeline,
            additional_objects=[
                (self.x_name.value,self.output_primary_objects_name.value),
                (self.y_name.value,self.output_secondary_objects_name.value),
                (self.output_primary_objects_name.value,self.output_secondary_objects_name.value)
            ] 
        )

    def get_categories(self, pipeline, object_name):
        result = []
        if object_name == self.x_name.value:
            result = [C_CHILDREN]
        elif object_name == self.y_name.value:
            result = [C_CHILDREN]
        elif object_name == "Image":
            result += [C_COUNT]
        elif object_name == self.output_primary_objects_name.value:
            result += [
                C_CHILDREN,
                C_LOCATION,
                C_NUMBER,
                C_PARENT
            ]
        elif object_name == self.output_secondary_objects_name.value:
            result += [
                C_LOCATION,
                C_NUMBER,
                C_PARENT
            ]
        return result

    def get_measurements(self, pipeline, object_name, category):
        if object_name == self.x_name.value:
            if category == C_CHILDREN:
                return ["%s_Count" % self.output_primary_objects_name.value]
        elif object_name == self.y_name.value:
            if category == C_CHILDREN:
                return ["%s_Count" % self.output_secondary_objects_name.value]
        elif object_name == self.output_primary_objects_name.value:
            if category == C_CHILDREN:
                return ["%s_Count" % self.output_secondary_objects_name.value]
            elif category == C_PARENT:
                return [self.x_name.value]
            elif category == C_LOCATION:
                return [
                    FTR_CENTER_X,
                    FTR_CENTER_Y,
                    FTR_CENTER_Z,
                ]
            elif category == C_NUMBER:
                return [FTR_OBJECT_NUMBER]
        elif object_name == self.output_secondary_objects_name.value: 
            if category == C_PARENT:
                return [self.y_name.value,self.output_primary_objects_name.value]
            elif category == C_LOCATION:
                return [
                    FTR_CENTER_X,
                    FTR_CENTER_Y,
                    FTR_CENTER_Z,
                ]
            elif category == C_NUMBER:
                return [FTR_OBJECT_NUMBER]

        elif (
            object_name == "Image"
            and category == C_COUNT
        ):
            return [self.output_primary_objects_name.value, 
                    self.output_secondary_objects_name.value]

        return []