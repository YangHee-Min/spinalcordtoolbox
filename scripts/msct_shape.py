#!/usr/bin/env python
########################################################################################################################
#
# This file contains useful functions for shape analysis based on spinal cord segmentation.
# The main input of these functions is a small image containing the binary spinal cord segmentation,
# ideally centered in the image.
#
# ----------------------------------------------------------------------------------------------------------------------
# Copyright (c) 2016 Polytechnique Montreal <www.neuro.polymtl.ca>
# Authors: Benjamin De Leener
# Modified: 2016-12-20
#
# About the license: see the file LICENSE.TXT
########################################################################################################################

# TODO: get rid of msct_shape and move content to process_seg

from __future__ import print_function, absolute_import, division

import math

import numpy as np

import tqdm
from skimage import measure, filters
from skimage.transform import warp, AffineTransform

import sct_utils as sct
from msct_types import Centerline
from spinalcordtoolbox.centerline.core import get_centerline


def smoothing(image, sigma=1.0):
    return filters.gaussian(image, sigma=sigma)


def properties2d(image, resolution=None):
    label_img = measure.label(np.transpose(image))
    regions = measure.regionprops(label_img)
    areas = [r.area for r in regions]
    ix = np.argsort(areas)
    if len(regions) != 0:
        sc_region = regions[ix[-1]]
        try:
            ratio_minor_major = sc_region.minor_axis_length / sc_region.major_axis_length
        except ZeroDivisionError:
            ratio_minor_major = 0.0

        area = sc_region.area  # TODO: increase precision (currently single decimal)
        diameter = sc_region.equivalent_diameter
        major_l = sc_region.major_axis_length
        minor_l = sc_region.minor_axis_length
        if resolution is not None:
            area *= resolution[0] * resolution[1]
            # TODO: compute length depending on resolution. Here it assume the patch has the same X and Y resolution
            diameter *= resolution[0]
            major_l *= resolution[0]
            minor_l *= resolution[0]

            size_grid = 8.0 / resolution[0]  # assuming the maximum spinal cord radius is 8 mm
        else:
            size_grid = int(2.4 * sc_region.major_axis_length)

        """
        import matplotlib.pyplot as plt
        plt.imshow(label_img)
        plt.text(1, 1, sc_region.orientation, color='white')
        plt.show()
        """

        sc_properties = {'area': area,
                         'bbox': sc_region.bbox,
                         'centroid': sc_region.centroid,
                         'eccentricity': sc_region.eccentricity,
                         'equivalent_diameter': diameter,
                         'euler_number': sc_region.euler_number,
                         'inertia_tensor': sc_region.inertia_tensor,
                         'inertia_tensor_eigvals': sc_region.inertia_tensor_eigvals,
                         'minor_axis_length': minor_l,
                         'major_axis_length': major_l,
                         'moments': sc_region.moments,
                         'moments_central': sc_region.moments_central,
                         'orientation': sc_region.orientation * 180.0 / math.pi,
                         'perimeter': sc_region.perimeter,
                         'ratio_minor_major': ratio_minor_major,
                         'solidity': sc_region.solidity  # convexity measure
                         # 'symmetry': dice_symmetry
                         }
    else:
        sc_properties = None

    return sc_properties


def assign_AP_and_RL_diameter(properties):
    """
    This script checks the orientation of the spinal cord and inverts axis if necessary to make sure the major axis is
    always labeled as right-left (RL), and the minor antero-posterior (AP).
    :param properties: dictionary generated by properties2d()
    :return: properties updated with new fields: AP_diameter, RL_diameter
    """
    if -45.0 < properties['orientation'] < 45.0:
        properties['RL_diameter'] = properties['major_axis_length']
        properties['AP_diameter'] = properties['minor_axis_length']
    else:
        properties['RL_diameter'] = properties['minor_axis_length']
        properties['AP_diameter'] = properties['major_axis_length']
    return properties


def compute_properties_along_centerline(im_seg, smooth_factor=5.0, interpolation_mode=0, algo_fitting='hanning',
                                        window_length=50, size_patch=7, remove_temp_files=1, verbose=1):
    """
    Compute shape property along spinal cord centerline. This algorithm computes the centerline,
    oversample it, extract 2D patch orthogonal to the centerline, compute the shape on the 2D patches, and finally
    undersample the shape information in order to match the input slice #.
    :param im_seg: Image of segmentation, already oriented in RPI
    :param smooth_factor:
    :param interpolation_mode:
    :param algo_fitting:
    :param window_length:
    :param remove_temp_files:
    :param verbose:
    :return:
    """
    # TODO: put size_patch back to 20 (was put to 7 for debugging purpose)
    # List of properties to output (in the right order)
    property_list = ['area',
                     'equivalent_diameter',
                     'AP_diameter',
                     'RL_diameter',
                     'ratio_minor_major',
                     'eccentricity',
                     'solidity',
                     'orientation']

    # Initiating some variables
    nx, ny, nz, nt, px, py, pz, pt = im_seg.dim

    # Extract min and max index in Z direction
    data_seg = im_seg.data
    X, Y, Z = (data_seg > 0).nonzero()
    min_z_index, max_z_index = min(Z), max(Z)

    # Define the resampling resolution. Here, we take the minimum of half the pixel size along X or Y in order to have
    # sufficient precision upon resampling. Since we want isotropic resamping, we take the min between the two dims.
    # resolution = min(float(px) / 2, float(py) / 2)
    # resolution = 0.5
    # Initialize 1d array with nan. Each element corresponds to a slice.
    properties = {key: np.full_like(np.empty(nz), np.nan, dtype=np.double) for key in property_list}
    # properties['incremental_length'] = np.full_like(np.empty(nz), np.nan, dtype=np.double)
    # properties['distance_from_C1'] = np.full_like(np.empty(nz), np.nan, dtype=np.double)
    # properties['vertebral_level'] = np.full_like(np.empty(nz), np.nan, dtype=np.double)
    # properties['z_slice'] = []

    # compute the spinal cord centerline based on the spinal cord segmentation
    _, arr_ctl, arr_ctl_der = get_centerline(im_seg, algo_fitting=algo_fitting, verbose=verbose)

    angles = np.full_like(np.empty(nz), np.nan, dtype=np.double)

    # Loop across z and compute shape analysis
    # TODO: add fancy progress bar
    for iz in range(min_z_index, max_z_index - 1):
        # Extract 2D patch
        current_patch = im_seg.data[:, :, iz]
        """ DEBUG
        from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
        from matplotlib.figure import Figure
        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.imshow(current_patch)
        fig.savefig('tmp_fig.png')
        """
        # Extract tangent vector to the centerline (i.e. its derivative)
        tangent_vect = np.array([arr_ctl_der[0][iz - min_z_index] * px,
                                 arr_ctl_der[1][iz - min_z_index] * py,
                                 pz])
        # Normalize vector by its L2 norm
        tangent_vect = tangent_vect / np.linalg.norm(tangent_vect)
        # Compute the angle between the centerline and the normal vector to the slice (i.e. u_z)
        v0 = [tangent_vect[0], tangent_vect[2]]
        v1 = [0, 1]
        angle_x = np.math.atan2(np.linalg.det([v0, v1]), np.dot(v0, v1))
        v0 = [tangent_vect[1], tangent_vect[2]]
        v1 = [0, 1]
        angle_y = np.math.atan2(np.linalg.det([v0, v1]), np.dot(v0, v1))
        # Apply affine transformation to account for the angle between the cord centerline and the normal to the patch
        tform = AffineTransform(scale=(np.cos(angle_x), np.cos(angle_y)))
        # TODO: make sure pattern does not go extend outside of image border
        current_patch_scaled = warp(current_patch,
                                    tform.inverse,
                                    output_shape=current_patch.shape,
                                    order=1,
                                    )
        # compute shape properties on 2D patch
        # TODO: adjust resolution in case anisotropic
        sc_properties = properties2d(current_patch_scaled, [px, py])
        # assign AP and RL to minor or major axis, depending on the orientation
        sc_properties = assign_AP_and_RL_diameter(sc_properties)
        # loop across properties and assign values for function output
        if sc_properties is not None:
            # properties['incremental_length'][iz] = centerline.incremental_length[i_centerline]
            for property_name in property_list:
                properties[property_name][iz] = sc_properties[property_name]
        else:
            sct.log.warning('No properties for slice: '.format([iz]))

    # # x_centerline_fit, y_centerline_fit, z_centerline = arr_ctl
    # # x_centerline_deriv, y_centerline_deriv = arr_ctl_der
    # # Transform centerline and derivatives to physical coordinate system
    # arr_ctl_phys = im_seg.transfo_pix2phys(
    #     [[arr_ctl[0][i], arr_ctl[1][i], arr_ctl[2][i]] for i in range(len(arr_ctl[0]))])
    # x_centerline, y_centerline, z_centerline = arr_ctl_phys[:, 0], arr_ctl_phys[:, 1], arr_ctl_phys[:, 2]
    # x_centerline_deriv, y_centerline_deriv = arr_ctl_der[0][:] * px, arr_ctl_der[1][:] * py
    # # TODO: maybe multiply by pz
    # centerline = Centerline(x_centerline, y_centerline, z_centerline, x_centerline_deriv, y_centerline_deriv,
    #                         np.ones_like(x_centerline_deriv))
    #
    # sct.printv('Computing spinal cord shape along the spinal cord...')
    # with tqdm.tqdm(total=len(range(min_z_index, max_z_index))) as pbar:
    #
    #     # Extracting patches perpendicular to the spinal cord and computing spinal cord shape
    #     i_centerline = 0  # index of the centerline() object
    #     for iz in range(min_z_index, max_z_index-1):
    #     # for index in range(centerline.number_of_points):  Julien
    #         # value_out = -5.0
    #         value_out = 0.0
    #         # TODO: correct for angulation using the cosine. The current approach has 2 issues:
    #         # - the centerline is not homogeneously sampled along z (which is the reason it is oversampled)
    #         # - computationally expensive
    #         # - requires resampling to higher resolution --> to check: maybe required with cosine approach
    #         current_patch = centerline.extract_perpendicular_square(im_seg, i_centerline, size=size_patch,
    #                                                                 resolution=resolution,
    #                                                                 interpolation_mode=interpolation_mode,
    #                                                                 border='constant', cval=value_out)
    #
    #         # check for pixels close to the spinal cord segmentation that are out of the image
    #         patch_zero = np.copy(current_patch)
    #         patch_zero[patch_zero == value_out] = 0.0
    #         # patch_borders = dilation(patch_zero) - patch_zero
    #
    #         """
    #         if np.count_nonzero(patch_borders + current_patch == value_out + 1.0) != 0:
    #             c = image.transfo_phys2pix([centerline.points[index]])[0]
    #             print('WARNING: no patch for slice', c[2])
    #             continue
    #         """
    #         # compute shape properties on 2D patch
    #         sc_properties = properties2d(patch_zero, [resolution, resolution])
    #         # assign AP and RL to minor or major axis, depending on the orientation
    #         sc_properties = assign_AP_and_RL_diameter(sc_properties)
    #         # loop across properties and assign values for function output
    #         if sc_properties is not None:
    #             # properties['incremental_length'][iz] = centerline.incremental_length[i_centerline]
    #             for property_name in property_list:
    #                 properties[property_name][iz] = sc_properties[property_name]
    #         else:
    #             c = im_seg.transfo_phys2pix([centerline.points[i_centerline]])[0]
    #             sct.printv('WARNING: no properties for slice', c[2])
    #
    #         i_centerline += 1
    #         pbar.update(1)

    # # smooth the spinal cord shape with a gaussian kernel if required
    # # TODO: remove this smoothing
    # if smooth_factor != 0.0:  # smooth_factor is in mm
    #     import scipy
    #     window = scipy.signal.hann(smooth_factor / np.mean(centerline.progressive_length))
    #     for property_name in property_list:
    #         properties[property_name] = scipy.signal.convolve(properties[property_name], window, mode='same') / np.sum(window)

    # extract all values for shape properties to be averaged across the oversampled centerline in order to match the
    # input slice #
    # sorting_values = []
    # for label in properties['z_slice']:
    #     if label not in sorting_values:
    #         sorting_values.append(label)
    # prepare output
    # shape_output = dict()
    # for property_name in property_list:
    #     shape_output[property_name] = []
    #     for label in sorting_values:
    #         averaged_shape[property_name].append(np.mean(
    #             [item for i, item in enumerate(properties[property_name]) if
    #              properties['z_slice'][i] == label]))
    # TODO: save angles

    return properties
