from cellprofiler_core.setting.text import Integer


class Boolean(Integer):
    """ A helper setting for boolean values, converting 0 to False and any other number to True
    """

    def __init__(self, text, value, *args, **kwargs):
        super().__init__(text, value, doc="""\
Enter '0' for \"False\" and any other value for \"True\"
""",
                         *args, **kwargs)

    def get_value(self, reraise=False):
        v = super().get_value(reraise)
        if v == 0:
            return False

        return True
