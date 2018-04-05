#!/usr/bin/env python
#########################################################################################
#
# Image processing API
#
# ---------------------------------------------------------------------------------------
# Copyright (c) 2018 Polytechnique Montreal <www.neuro.polymtl.ca>
#
# About the license: see the file LICENSE.TXT
#########################################################################################

import sys, os

import numpy as np
import skimage.filters

import msct_image


def apply_on_path_or_image_or_ndarray(func, src, dst=None, dst_creator=None,
 dst_suffix=None, *args, **kw):
    """
    Apply `func(src, dst, *args, **kw)` on transformed `src` & `dst`.

    The following rules:

    - if src and dst are provided, they are used
    - if dst is None, it will be created and match src's type
    - src and dst can be paths to Image, or Image, or numpy ndarrays.

    :param func: function to call as `func(src_array, dst_array, *args, **kw)`,
    :param src: input filename, or Image, or ndarray
    :param dst: output filename, or Image, or ndarray
    :return: dst

    """

    if dst_suffix is None:
        dst_suffix = func.__name__

    if isinstance(src, str):
        src_path = src
        src_image = msct_image.Image(src_path)
        src = src_image.data
    elif isinstance(src, msct_image.Image):
        src_image = src
        src_path = None
        src = src_image.data
    elif isinstance(src, np.ndarray):
        src_path = None
        src_image = None
    else:
        raise NotImplementedError("unknown type {} for src".format(type(src)))

    if isinstance(dst, str):
        dst_path = dst
        dst_image = src_image.copy()
        dst_image.setFilename(dst_path)
        dst = dst_image.data
    elif isinstance(dst, msct_image.Image):
        dst_path = None
        dst_image = dst
        dst = dst.data
    elif isinstance(dst, np.ndarray):
        dst_path = None
        dst_image = None
    elif dst is None:
        if src_path is not None:
            folder, basename, ext = src_image.path, src_image.file_name, src_image.ext
            dst_path = os.path.join(folder, "{}_{}{}".format(basename, dst_suffix, ext))
            dst_image = src_image.copy()
            dst_image.setFileName(dst_path)
        elif src_image is not None:
            dst_image = src_image.copy()
            dst_image.setFileName("")
            dst_path = None
        else:
            dst = dst_creator(src)
    else:
        raise NotImplementedError("unknown type {} for dst".format(type(src)))


    _ = func(src, dst, *args, **kw)

    if dst_path is not None:
        dst_image.save()
        return dst_path
    elif dst_image is not None:
        return dst_image

    return dst


def binarize_ndarray(src, dst=None, threshold=None):
    """
    Binarize an array.

    :param src: input ndarray
    :param dst: optional output ndarray, created as byte array if not provided
    :param threshold: threshold for binarization, "otsu" to use Otsu's threshold
    :return: dst (for use if parameter dst is None)
    """

    if dst is None:
        dst = np.zeros_like(src, dtype=np.uint8)

    if threshold == "otsu":
        threshold = skimage.filters.threshold_otsu(src)
    else:
        try:
            threshold += 0
        except:
            raise NotImplementedError("unknown threshold {}".format(threshold))

    dst[:] = src >= threshold

    return dst



def binarize(src, dst=None, threshold=None):
    """
    Binarize an Image
    """

    return apply_on_path_or_image_or_ndarray(
     func=binarize_ndarray,
     src=src,
     dst=dst,
     dst_creator=lambda src: np.zeros_like(src, dtype=np.uint8),
     dst_suffix="bin",
     threshold=threshold,
    )


if __name__ == "__main__":
    dst = binarize("t2.nii.gz", threshold="otsu")
    print(dst)

    src = msct_image.Image("t2.nii.gz")
    dst = msct_image.Image("t2_bin.nii.gz")
    dst = binarize(src, dst, threshold="otsu")
    print(dst)