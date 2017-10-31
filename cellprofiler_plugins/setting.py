""" Settings.py - GUIs for module settings
"""

import cellprofiler.setting

class MeasurementMultiChoiceForCategory(cellprofiler.setting.MeasurementMultiChoice):
    '''A multi-choice setting for selecting multiple measurements within a given category'''

    def __init__(self, text, category_chooser, value='', *args, **kwargs):
        '''Initialize the measurement multi-choice

        At initialization, the choices are empty because the measurements
        can't be fetched here. It's done (bit of a hack) in test_valid.
        '''
        super(cellprofiler.setting.MeasurementMultiChoice, self).__init__(text, [], value, *args, **kwargs)
        self.category_chooser = category_chooser

    def populate_choices(self, pipeline):
        #
        # Find our module
        #
        for module in pipeline.modules():
            for setting in module.visible_settings():
                if id(setting) == id(self):
                    break
        columns = pipeline.get_measurement_columns(module)

        def valid_mc(c):
            '''Disallow any measurement column with "," or "|" in its names. Must be from specified category.'''
            return not any([any([bad in f for f in c[:2]]) for bad in ",", "|"]) and c[0] == self.category_chooser.get_value()

        self.set_choices([self.make_measurement_choice(c[0], c[1])
                          for c in columns if valid_mc(c)])