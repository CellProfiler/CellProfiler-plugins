# -*- coding: utf-8 -*-
"""
Index is a convenient structure for processing calculate all angle x radius point in one numpy operation.
Date: 2013-2016
Website: http://cellstar-algorithm.org/
"""

import numpy as np


class Index(object):
    @classmethod
    def create(cls, px, py):
        return np.column_stack((py.flat, px.flat)).astype(np.int64)

    @staticmethod
    def to_numpy(index):
        if len(index.shape) == 2:
            return index[:, 0], index[:, 1]
        elif len(index.shape) == 3:
            return index[:, :, 0], index[:, :, 1]
        else:
            return index
