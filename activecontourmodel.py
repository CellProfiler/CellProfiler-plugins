# coding=utf-8

"""

Active contour model

"""

import textwrap
import cellprofiler.module
import cellprofiler.object
import cellprofiler.setting
import numpy
import scipy.ndimage
import skimage.draw
import skimage.morphology
import skimage.filters
import skimage.measure
import skimage.segmentation


DIFFERENTIAL_METHOD = "Partial differential equation Chan-Vese"
MORPH_GEODESIC_METHOD = "Morphological geodesic"
MORPH_CHAN_VESE_METHOD = "Morphological Chan-Vese"
LEVEL_SET_CIRCLE = "circle"
LEVEL_SET_CHECKERBOARD = "checkerboard"


class DefaultCoordinate(cellprofiler.setting.Coordinates):
    """
    Override for the Coordinate setting to allow negative defaults.
    """
    def test_valid(self, pipeline):
        # TODO: fix this for 3d images
        values = self.value_text.split(',')
        if len(values) < 2:
            raise cellprofiler.setting.ValidationError("X and Y values must be separated by a comma", self)
        if len(values) > 2:
            raise cellprofiler.setting.ValidationError("Only two values allowed", self)
        for value in values:
            try:
                int(value.strip())
            except ValueError:
                raise cellprofiler.setting.ValidationError("{} is not an integer".format(value), self)


class ActiveContourModel(cellprofiler.module.ImageSegmentation):
    module_name = "Active contour model"

    variable_revision_number = 2

    def create_settings(self):
        super(ActiveContourModel, self).create_settings()

        self.method = cellprofiler.setting.Choice(
            text="Active contour method",
            choices=[DIFFERENTIAL_METHOD,
                     MORPH_GEODESIC_METHOD,
                     MORPH_CHAN_VESE_METHOD],
            value=DIFFERENTIAL_METHOD,
        )

        # Shared by all three methods
        self.iterations = cellprofiler.setting.Integer(
            text="Iterations",
            value=20
        )

        # Only shared by PDE and GEODESIC
        self.threshold = cellprofiler.setting.Float(
            text="Threshold",
            value=0
        )

        # Pre-processing settings
        self.pde_alpha = cellprofiler.setting.Float(
            text="Alpha",
            value=0.2
        )

        self.advanced_settings = cellprofiler.setting.Binary(
            text="Advanced settings for PDE method",
            value=False
        )

        self.phi_bound = cellprofiler.setting.Float(
            text="Phi bound",
            value=1.2
        )

        self.pre_threshold = cellprofiler.setting.Float(
            text="Pre-thresholding factor",
            value=0.9
        )

        self.connectivity = cellprofiler.setting.Integer(
            text="Label connectivity",
            value=1
        )

        self.cfl_factor = cellprofiler.setting.Float(
            text="CFL condition maintenance factor",
            value=0.45
        )

        self.sdf_smoothing = cellprofiler.setting.Float(
            text="SDF smoothing factor",
            value=0.5
        )

        # Shared morph settings
        self.alpha = cellprofiler.setting.Float(
            text="Alpha",
            value=100.0
        )

        self.sigma = cellprofiler.setting.Float(
            text="Sigma",
            value=5.0
        )

        self.level_set = cellprofiler.setting.Choice(
            text="Initial level set",
            choices=[LEVEL_SET_CIRCLE, LEVEL_SET_CHECKERBOARD],
            value=LEVEL_SET_CIRCLE
        )

        self.adv_level_set = cellprofiler.setting.Binary(
            text="Advanced level set options",
            value=False
        )

        self.circle_center = DefaultCoordinate(
            text="Circle level set center",
            value=(-1, -1)
        )

        self.level_set_iterative = cellprofiler.setting.Binary(
            text="Enable iterative level set determination",
            value=False,
            doc=textwrap.dedent("""
            The region that gets segmented for shape-based level set is 
            determined largely by the level set size and the inner/outer region 
            weighting. This means that sometimes, the "segmented" region will 
            not match the region of interest (e.g. the space *between* nuclei 
            will be segmented, rather than the nuclei themselves). This allows 
            you to specify multiple level sets to try while attempting to segment 
            a given region. The foreground/background relationship is determined 
            by first attempting the segmentation with 10% of the defined iterations 
            and then comparing the median intensity of the original image that's 
            contained within each region. The region with the greatest median 
            intensity is assigned to be the foreground.
            """)
        )

        self.level_set_size = cellprofiler.setting.Float(
            text="Level set size",
            value=-1.,
            minval=0.,
            doc=textwrap.dedent("""
            For **{LEVEL_SET_CIRCLE}** this can be a float and corresponds to 
            the circle radius.
            
            For **{LEVEL_SET_CHECKERBOARD}** this is cast to an integer and
            corresponds to the checkerbox width/height.
            """.format(
                LEVEL_SET_CIRCLE=LEVEL_SET_CIRCLE,
                LEVEL_SET_CHECKERBOARD=LEVEL_SET_CHECKERBOARD
            ))

        )

        self.level_set_iterative_sizes = cellprofiler.setting.Text(
            text="Level set sizes",
            value="8,3,1",
            doc=textwrap.dedent("""
            A list of sizes to try, in order, separated by commas.
            
            For **{LEVEL_SET_CIRCLE}** this can be a list of floats and 
            corresponds to the circle radius.
            
            For **{LEVEL_SET_CHECKERBOARD}** this is a list of integers (floating 
            points are casted to integers) and corresponds to the checkerboard width/height.
            
            E.g. "8,5,2,1" or "18, 3, 4" or "8.5, 2.3, 4.0"
            """.format(
                LEVEL_SET_CIRCLE=LEVEL_SET_CIRCLE,
                LEVEL_SET_CHECKERBOARD=LEVEL_SET_CHECKERBOARD
            ))
        )

        self.smoothing = cellprofiler.setting.Integer(
            text="Smoothing",
            value=1,
            minval=0
        )

        # Geodesic settings
        self.balloon = cellprofiler.setting.Float(
            text="Balloon force",
            value=0.
        )

        # Morph Chan-Vese settings
        self.outer_weight = cellprofiler.setting.Float(
            text="Outer region weight",
            value=1.
        )

        self.inner_weight = cellprofiler.setting.Float(
            text="Inner region weight",
            value=1.
        )

    def settings(self):
        __settings__ = super(ActiveContourModel, self).settings()

        return __settings__ + [
            self.method,
            self.iterations,
            self.threshold,
            self.pde_alpha,
            self.advanced_settings,
            self.phi_bound,
            self.pre_threshold,
            self.connectivity,
            self.cfl_factor,
            self.sdf_smoothing,
            self.alpha,
            self.sigma,
            self.level_set,
            self.adv_level_set,
            self.circle_center,
            self.level_set_size,
            self.smoothing,
            self.balloon,
            self.outer_weight,
            self.inner_weight,
            self.level_set_iterative,
            self.level_set_iterative_sizes
        ]

    def validate_module(self, pipeline):
        # Parse the iterative sizes
        iterative_sizes = self.level_set_iterative_sizes.value
        split_sizes = [x.strip() for x in iterative_sizes.split(',')]
        try:
            self.parse_level_set_values()
        except ValueError:
            raise cellprofiler.setting.ValidationError("'{}' is not a suitable list of values for {} level set!"
                                                       .format(iterative_sizes, self.level_set.value),
                                                       self.level_set_iterative_sizes)

        # Validate circle coordinate settings
        if self.adv_level_set.value:
            center_x = self.circle_center.x
            center_y = self.circle_center.y
            if not ((center_x == center_y == -1) or (center_x != -1 and center_y != -1)):
                raise cellprofiler.setting.ValidationError("Circle coordinates must either both be -1 (default) or both positive",
                                                           self.circle_center)

    def upgrade_settings(self, setting_values, variable_revision_number, module_name, from_matlab):
        if variable_revision_number == 1:
            # The circle and checkerboard level set sizes were unified
            __settings__ = setting_values[:17] + setting_values[18:]

            variable_revision_number = 2

        else:
            __settings__ = setting_values

        return __settings__, variable_revision_number, from_matlab

    def visible_settings(self):
        __settings__ = super(ActiveContourModel, self).settings()

        # Shared by all three methods
        __settings__ += [
            self.method,
            self.iterations,
        ]

        # Add PDE settings
        if self.method.value == DIFFERENTIAL_METHOD:
            __settings__ += [
                self.pde_alpha,
                self.threshold,
                self.advanced_settings,
            ]
            if self.advanced_settings.value:
                __settings__ += [
                    self.phi_bound,
                    self.pre_threshold,
                    self.connectivity,
                    self.cfl_factor,
                    self.sdf_smoothing
                ]

        # Add common settings
        elif self.method.value in [MORPH_GEODESIC_METHOD, MORPH_CHAN_VESE_METHOD]:
            __settings__ += [
                self.alpha,
                self.sigma,
                self.level_set,
                self.adv_level_set,
            ]

            # Advanced settings for level setting
            if self.adv_level_set.value:
                __settings__ += [
                    self.level_set_iterative
                ]

                # Determine which size/sizes option to show
                # based on the iterative setting
                if self.level_set_iterative.value:
                    __settings__ += [
                        self.level_set_iterative_sizes
                    ]
                else:
                    __settings__ += [
                        self.level_set_size
                    ]

                # Extra parameter for the circle level set
                if self.level_set.value == LEVEL_SET_CIRCLE:
                    __settings__ += [
                        self.circle_center,
                    ]

            # Add common smoothing function after level setting options
            __settings__ += [
                self.smoothing
            ]
            # Add individual settings
            if self.method.value == MORPH_GEODESIC_METHOD:
                __settings__ += [
                    self.threshold,
                    self.balloon
                ]
            elif self.method.value == MORPH_CHAN_VESE_METHOD:
                __settings__ += [
                    self.outer_weight,
                    self.inner_weight
                ]
        return __settings__

    def parse_level_set_values(self):
        iterative_sizes = self.level_set_iterative_sizes.value
        split_sizes = [x.strip() for x in iterative_sizes.split(',')]
        if self.level_set.value == LEVEL_SET_CIRCLE:
            parse_fn = float
        else:
            # The users could specify them as floats, but for checkerboard they need
            # to be converted to ints. `ceil` is used here just to make sure 0.x is
            # still a valid checkerboard size.
            parse_fn = lambda y: int(numpy.ceil(float(y)))
        return [parse_fn(x) for x in split_sizes]

    def generate_level_set(self, shape, size=None):
        """
        Generate a level set based off of the current settings and
        optionally a specific size.
        :param shape: Shape of the level set to make
        :type shape: tuple
        :param size: Radius or width/height for the given level set
        :type size: float, int
        :return:
        :rtype:
        """
        # Return early if the advanced options weren't asked for
        if not self.adv_level_set.value:
            return str(self.level_set.value)

        if self.level_set.value == LEVEL_SET_CIRCLE:
            # TODO: fix this for 3d images
            radius = self.level_set_size.value if size is None else size
            center_x = self.circle_center.x
            center_y = self.circle_center.y
            if center_x == center_y == -1:
                center = None
            else:
                if len(shape) == 3:
                    raise NotImplementedError("3D center selection not yet implemented")
                center = (center_x, center_y)
            return skimage.segmentation.circle_level_set(shape, center=center, radius=radius)

        elif self.level_set.value == LEVEL_SET_CHECKERBOARD:
            square_size = int(numpy.ceil(self.level_set_size.value)) if size is None else size
            return skimage.segmentation.checkerboard_level_set(shape, square_size=square_size)

    def run_morphological_operations(self, data, size=None, iterations=None):
        level_set = self.generate_level_set(data.shape, size)
        iterations = self.iterations.value if iterations is None else iterations

        if self.method.value == MORPH_GEODESIC_METHOD:
            # Perform preprocessing for geodesic method
            pre_process = skimage.segmentation.inverse_gaussian_gradient(data,
                                                                         alpha=self.alpha.value,
                                                                         sigma=self.sigma.value)

            threshold_policy = 'auto' if self.threshold.value == 0 else self.threshold.value

            return skimage.segmentation.morphological_geodesic_active_contour(pre_process,
                                                                              iterations=iterations,
                                                                              smoothing=self.smoothing.value,
                                                                              init_level_set=level_set,
                                                                              threshold=threshold_policy,
                                                                              balloon=self.balloon.value)

        elif self.method.value == MORPH_CHAN_VESE_METHOD:
            return skimage.segmentation.morphological_chan_vese(data,
                                                                iterations=iterations,
                                                                smoothing=self.smoothing.value,
                                                                init_level_set=level_set,
                                                                lambda1=self.outer_weight.value,
                                                                lambda2=self.inner_weight.value)

    def run(self, workspace):
        x_name = self.x_name.value

        y_name = self.y_name.value

        images = workspace.image_set

        x = images.get_image(x_name)

        x_data = x.pixel_data

        y_data = None

        if self.method.value == DIFFERENTIAL_METHOD:
            thresholding = skimage.filters.threshold_otsu(x_data)

            thresholding = thresholding * self.pre_threshold.value

            binary = x_data > thresholding

            y_data, phi = chan_vese(x_data,
                                    binary,
                                    alpha=self.pde_alpha.value,
                                    iterations=self.iterations.value,
                                    threshold=self.threshold.value,
                                    phi_bound=self.phi_bound.value,
                                    cfl_factor=self.cfl_factor.value,
                                    sdf_smoothing=self.sdf_smoothing.value)

        else:
            # Do a single run and return the result
            if not self.level_set_iterative.value:
                y_data = self.run_morphological_operations(x_data)

            # Step through each proposed level set size, try 10% of the initial iterations,
            # and check to see that the foreground/background relationship is preserved
            else:
                iterative_sizes = self.parse_level_set_values()
                # We only want to "try out" the first few iterations, so we'll take 10%
                iterations = int(numpy.ceil(self.iterations.value * 0.1))
                for level_set_size in iterative_sizes:
                    test_segmentation = self.run_morphological_operations(x_data,
                                                                          size=level_set_size,
                                                                          iterations=iterations)
                    # Convert it to boolean because we want to use it as a mask
                    test_segmentation = test_segmentation.astype(bool)
                    # Compare the foreground and background median intensities
                    fg_median = numpy.median(x_data[test_segmentation])
                    bg_median = numpy.median(x_data[~test_segmentation])
                    if fg_median > bg_median:
                        # We're good to go!
                        print("Suitable level set size found: {}".format(level_set_size))
                        break

                # If we're here, we haven't found a suitable level set size within the supplied
                # level set values (i.e. we didn't `break` in the above code block)
                else:
                    raise ValueError("None of the supplied level set sizes produced a suitable "
                                     "foreground/background relationship. Values: {}".format(iterative_sizes))

                # If we're here, we broke out of the for loop above and level_set_size should
                # be a suitable size for finding the correct relationship. We also want to
                # use the iteration count that the user supplied rather than the 10% reduced here.
                y_data = self.run_morphological_operations(x_data, level_set_size)

        y_data = skimage.measure.label(y_data, connectivity=self.connectivity.value)

        objects = cellprofiler.object.Objects()

        objects.segmented = y_data

        objects.parent_image = x

        workspace.object_set.add_objects(objects, y_name)

        self.add_measurements(workspace)

        if self.show_window:
            workspace.display_data.x_data = x_data

            workspace.display_data.y_data = y_data

            workspace.display_data.dimensions = x.dimensions


epsilon = numpy.finfo(numpy.float).eps


def chan_vese(image, mask, iterations, alpha, threshold, phi_bound, cfl_factor, sdf_smoothing):
    image = skimage.img_as_float(image)

    # -- Create a signed distance map (SDF) from mask
    phi = bwdist(mask) - bwdist(1 - mask) + mask - 0.5

    # --main loop
    iteration = 0

    stop = False

    previous_mask = mask

    c = 0

    while iteration < iterations and not stop:
        # get the curve's narrow band
        index = numpy.flatnonzero(numpy.logical_and(phi <= phi_bound, phi >= -phi_bound))

        if len(index) > 0:
            interior_points = numpy.flatnonzero(phi <= 0)

            exterior_points = numpy.flatnonzero(phi > 0)

            interior_mean = numpy.sum(image.flat[interior_points]) / (len(interior_points) + epsilon)

            exterior_mean = numpy.sum(image.flat[exterior_points]) / (len(exterior_points) + epsilon)

            force = (image.flat[index] - interior_mean) ** 2 - (image.flat[index] - exterior_mean) ** 2

            curvature = get_curvature(phi, index)

            gradient_descent = force / numpy.max(numpy.abs(force)) + alpha * curvature

            # -- maintain the CFL condition
            dt = cfl_factor / (numpy.max(numpy.abs(gradient_descent)) + epsilon)

            # -- evolve the curve
            phi.flat[index] += dt * gradient_descent

            # -- Keep SDF smooth
            phi = sussman(phi, sdf_smoothing)

            new_mask = phi <= 0

            c = convergence(previous_mask, new_mask, threshold, c)

            if c <= 5:
                iteration += 1

                previous_mask = new_mask
            else:
                stop = True

        else:
            break

    # -- make mask from SDF
    segmentation = phi <= 0  # -- Get mask from levelset

    return segmentation, phi


def bwdist(a):
    """
    this is an intermediary function, 'a' has only True, False vals,
    so we convert them into 0, 1 values -- in reverse. True is 0,
    False is 1, distance_transform_edt wants it that way.
    """
    return scipy.ndimage.distance_transform_edt(a == 0)


# -- compute curvature along SDF
def get_curvature(phi, index):
    dimz, dimy, dimx = phi.shape
    zyx = numpy.array([numpy.unravel_index(i, phi.shape) for i in index])  # get subscripts
    z = zyx[:, 0]
    y = zyx[:, 1]
    x = zyx[:, 2]

    # -- get subscripts of neighbors
    zm1 = z - 1
    ym1 = y - 1
    xm1 = x - 1
    zp1 = z + 1
    yp1 = y + 1
    xp1 = x + 1

    # -- bounds checking
    zm1[zm1 < 0] = 0
    ym1[ym1 < 0] = 0
    xm1[xm1 < 0] = 0
    zp1[zp1 >= dimz] = dimz - 1
    yp1[yp1 >= dimy] = dimy - 1
    xp1[xp1 >= dimx] = dimx - 1

    # -- get central derivatives of SDF at x,y
    dx = (phi[z, y, xm1] - phi[z, y, xp1]) / 2  # (l-r)/2

    dxx = phi[z, y, xm1] - 2 * phi[z, y, x] + phi[z, y, xp1]  # l-2c+r

    dx2 = dx * dx

    dy = (phi[z, ym1, x] - phi[z, yp1, x]) / 2  # (u-d)/2

    dyy = phi[z, ym1, x] - 2 * phi[z, y, x] + phi[z, yp1, x]  # u-2c+d

    dy2 = dy * dy

    dz = (phi[zm1, y, x] - phi[zp1, y, x]) / 2  # (b-f)/2

    dzz = phi[zm1, y, x] - 2 * phi[z, y, x] + phi[zp1, y, x]  # b-2c+f

    dz2 = dz * dz

    # (ul+dr-ur-dl)/4
    dxy = (phi[z, ym1, xm1] + phi[z, yp1, xp1] - phi[z, ym1, xp1] - phi[z, yp1, xm1]) / 4

    # (lf+rb-rf-lb)/4
    dxz = (phi[zp1, y, xm1] + phi[zm1, y, xp1] - phi[zp1, y, xp1] - phi[zm1, y, xm1]) / 4

    # (uf+db-df-ub)/4
    dyz = (phi[zp1, ym1, x] + phi[zm1, yp1, x] - phi[zp1, yp1, x] - phi[zm1, ym1, x]) / 4

    # -- compute curvature (Kappa)
    curvature = ((dxx * (dy2 + dz2) + dyy * (dx2 + dz2) + dzz * (dx2 + dy2) - 2 * dx * dy * dxy - 2 * dx * dz * dxz - 2 * dy * dz * dyz) / (dx2 + dy2 + dz2 + epsilon))

    return curvature


def mymax(a, b):
    return (a + b + numpy.abs(a - b)) / 2


# -- level set re-initialization by the sussman method
def sussman(D, dt):
    # forward/backward differences
    a = D - shiftr(D)  # backward

    b = shiftl(D) - D  # forward

    c = D - shiftd(D)  # backward

    d = shiftu(D) - D  # forward

    e = D - shiftf(D)  # backward

    f = shiftb(D) - D  # forward

    a_p = a
    a_n = a.copy()  # a+ and a-
    b_p = b
    b_n = b.copy()
    c_p = c
    c_n = c.copy()
    d_p = d
    d_n = d.copy()
    e_p = e
    e_n = e.copy()
    f_p = f
    f_n = f.copy()

    a_p[a < 0] = 0
    a_n[a > 0] = 0
    b_p[b < 0] = 0
    b_n[b > 0] = 0
    c_p[c < 0] = 0
    c_n[c > 0] = 0
    d_p[d < 0] = 0
    d_n[d > 0] = 0

    dD = numpy.zeros(D.shape)
    D_neg_ind = numpy.flatnonzero(D < 0)
    D_pos_ind = numpy.flatnonzero(D > 0)

    dD.flat[D_pos_ind] = numpy.sqrt(mymax(a_p.flat[D_pos_ind] ** 2, b_n.flat[D_pos_ind] ** 2)
                                    + mymax(c_p.flat[D_pos_ind] ** 2, d_n.flat[D_pos_ind] ** 2)
                                    + mymax(e_p.flat[D_pos_ind] ** 2, f_n.flat[D_pos_ind] ** 2)
                                    ) - 1

    dD.flat[D_neg_ind] = numpy.sqrt(mymax(a_n.flat[D_neg_ind] ** 2, b_p.flat[D_neg_ind] ** 2)
                                    + mymax(c_n.flat[D_neg_ind] ** 2, d_p.flat[D_neg_ind] ** 2)
                                    + mymax(e_n.flat[D_neg_ind] ** 2, f_p.flat[D_neg_ind] ** 2)
                                    ) - 1

    D = D - dt * numpy.sign(D) * dD

    return D


# -- whole matrix derivatives
def shiftd(m):
    return m[:, range(1, m.shape[1]) + [m.shape[1] - 1], :]


def shiftl(m):
    return m[:, :, range(1, m.shape[2]) + [m.shape[2] - 1]]


def shiftr(m):
    return m[:, :, [0] + range(0, m.shape[2] - 1)]


def shiftu(m):
    return m[:, [0] + range(0, m.shape[1] - 1), :]


def shiftf(m):
    return m[[0] + range(0, m.shape[0] - 1), :, :]


def shiftb(m):
    return m[range(1, m.shape[0]) + [m.shape[0] - 1], :, :]


# Convergence Test
def convergence(p_mask, n_mask, thresh, c):
    if numpy.sum(numpy.abs(numpy.logical_xor(p_mask, n_mask))) < thresh:
        c += 1
    else:
        c = 0

    return c

