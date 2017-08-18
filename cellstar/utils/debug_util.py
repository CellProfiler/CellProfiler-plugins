# -*- coding: utf-8 -*-
"""
Utilities with tools that can help with debuging / profiling CellStar
Date: 2016
Website: http://cellstar-algorithm.org/
"""

import os
from os import makedirs
from os.path import exists

import numpy as np
import scipy as sp

from cellstar.core import image_repo

debug_image_path = "debug"

# profiling switches
PROFILE_SPEED = False
PROFILE_MEMORY = False

# main switch which turn off all debugging utils (always deploy with False)
DEBUGING = False
SHOW = False

SNAKE_PROPERTIES = False
# allow the user to inspect cell star results before segmentation (only for debugging)
EXPLORE = False

# pyplot import can fail if cellstar used as a plugin
try:
    import matplotlib
    import matplotlib.pyplot as plt

    if not SHOW:
        try:
            matplotlib.use('Agg')
        except:
            pass
except:
    DEBUGING = False  # turn off debugging images if unavailable (e.g. in CP 2.2 BETA)

# try to load user32.dll for key lock state
user32_dll = None
try:
    import ctypes
    user32_dll = ctypes.WinDLL ("User32.dll")
    user32_dll.GetKeyState.restype = ctypes.c_short
except:
    pass


def check_caps_scroll_state():
    if user32_dll is None:
        return None, None

    VK_CAPITAL = 0x14
    VK_SCROLL = 0X91
    return user32_dll.GetKeyState(VK_CAPITAL), user32_dll.GetKeyState(VK_SCROLL)


def prepare_debug_folder():
    if not exists(debug_image_path):
        makedirs(debug_image_path)


def draw_seeds_on_axes(seeds, axes):
    if DEBUGING:
        return axes.plot([s.x for s in seeds], [s.y for s in seeds], 'bo', markersize=3)


def draw_seeds(seeds, background, title="some_source"):
    if DEBUGING:
        prepare_debug_folder()
        fig = plt.figure("draw_seeds")
        fig.frameon = False
        plt.imshow(background, cmap=plt.cm.gray)
        plt.plot([s.x for s in seeds], [s.y for s in seeds], 'bo', markersize=3)
        plt.savefig(os.path.join(debug_image_path, "seeds_" + title + ".png"), pad_inches=0.0)
        fig.clf()
        plt.close(fig)


def images_repo_save(images):
    """
    @type images: image_repo.ImageRepo
    """
    image_save(images.background, "background")
    image_save(images.brighter, "brighter")
    image_save(images.brighter_original, "brighter_original")
    image_save(images.darker, "darker")
    image_save(images.darker_original, "darker_original")
    image_save(images.cell_content_mask, "cell_content_mask")
    image_save(images.cell_border_mask, "cell_border_mask")
    image_save(images.foreground_mask, "foreground_mask")
    image_save(images.mask, "image_mask")
    image_save(images.image_back_difference, "image_back_difference")


def image_save(image, title):
    """
    Displays image with title using matplotlib.pyplot
    @param image:
    @param title:
    """
    if DEBUGING:
        prepare_debug_folder()
        file_path = os.path.join(debug_image_path, title + '.tif')
        sp.misc.imsave(file_path, image)
        return file_path
    return None


def image_show(image, title, override=False):
    """
    Displays image with title using matplotlib.pyplot
    @param image:
    @param title:
    """
    if DEBUGING and (SHOW or override):
        prepare_debug_folder()
        fig = plt.figure(title)
        plt.imshow(image, cmap=plt.cm.gray, interpolation='none')
        plt.show()
        fig.clf()
        plt.close(fig)


def draw_overlay(image, x, y):
    if DEBUGING and SHOW:
        prepare_debug_folder()
        fig = plt.figure()
        plt.imshow(image, cmap=plt.cm.gray, interpolation='none')
        plt.plot(x, y)
        plt.show()
        fig.clf()
        plt.close(fig)


def explorer_expected():
    if DEBUGING:
        check_state = check_caps_scroll_state()
        if EXPLORE or check_state[0] == True and check_state[1] == True:
            return True
    return False


def explore_cellstar(cellstar=None, seeds=[], snakes=[], images=None, image=None, params=None):
    if explorer_expected():
        value = 0
        try:
            app = None
            try:
                import wx
                app = wx.App(0)
            except:
                pass

            import utils.explorer as exp
            if image is None:
                image = cellstar.images.image
            if images is None:
                images = cellstar.images

            explorer_ui = exp.ExplorerFrame(images)
            explorer = exp.Explorer(image, images, explorer_ui, cellstar, params)
            explorer.stick_seeds = seeds
            explorer.stick_snakes = snakes
            value = explorer_ui.ShowModal()

            #if app is not None:
            #    app.MainLoop()
        except Exception as ex:
            print ex
            pass

        if value == exp.ExplorerFrame.ABORTED:
            raise Exception("Execution aborted")


def draw_snakes_on_axes(snakes, axes, outliers=.1):
    if DEBUGING and len(snakes) >= 1:
        snakes = sorted(snakes, key=lambda ss: ss.rank)
        snakes_tc = snakes[:max(1, int(len(snakes) * (1 - outliers)))]

        max_rank = snakes_tc[-1].rank
        min_rank = snakes_tc[0].rank

        rank_range = max_rank - min_rank
        if rank_range == 0:  # for example there is one snake
            rank_range = max_rank

        rank_ci = lambda rank: 999 * ((rank - min_rank) / rank_range) if rank <= max_rank else 999
        colors = plt.cm.jet(np.linspace(0, 1, 1000))
        s_colors = [colors[int(rank_ci(s.rank))] for s in snakes]

        # we want the best on top
        for snake, color in reversed(zip(snakes, s_colors)):
            axes.plot(snake.xs, snake.ys, c=color, linewidth=1.0)


def draw_snakes(image, snakes, outliers=.1, it=0):
    if DEBUGING and len(snakes) > 1:
        prepare_debug_folder()

        fig = plt.figure("draw_snakes")
        plt.imshow(image, cmap=plt.cm.gray, interpolation='none')
        draw_snakes_on_axes(snakes, plt)

        plt.savefig(os.path.join(debug_image_path, "snakes_rainbow_" + str(it) + ".png"), pad_inches=0.0)
        if SHOW:
            plt.show()

        fig.clf()
        plt.close(fig)

try:
    import line_profiler
    import memory_profiler
except:
    pass


def speed_profile(func):
    def profiled_func(*args, **kwargs):
        try:
            profiler = line_profiler.LineProfiler()
            profiler.add_function(func)
            profiler.enable_by_count()
            return func(*args, **kwargs)
        finally:
            profiler.print_stats()

    if PROFILE_SPEED:
        return profiled_func
    else:
        return func


def memory_profile(func):
    if not PROFILE_MEMORY:
        return func
    else:
        if func is not None:
            def wrapper(*args, **kwargs):
                if PROFILE_MEMORY:
                    prof = memory_profiler.LineProfiler()
                    val = prof(func)(*args, **kwargs)
                    memory_profiler.show_results(prof)
                else:
                    val = func(*args, **kwargs)
                return val

            return wrapper
        else:
            def inner_wrapper(f):
                return memory_profiler.profile(f)

            return inner_wrapper
