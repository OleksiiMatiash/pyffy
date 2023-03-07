from numpy import float32, ndarray, uint16

import pyffyCommon
from pyffyExif import PyffyExif
from pyffySettings import PyffySettings


def bitwiseMask(image: ndarray[uint16], exif: PyffyExif, bits: int, leaveLSB: bool) -> ndarray[uint16]:
    activeAreaImage = pyffyCommon.getActiveAreaPixels(image, exif.imageHeight, exif.imageWidth, exif.activeArea)
    activeAreaImage -= pyffyCommon.getBlackWhiteLevel(exif.blackLevels, 0)
    activeAreaImage = pyffyCommon.bitwiseMask(activeAreaImage, bits, leaveLSB)
    activeAreaImage += pyffyCommon.getBlackWhiteLevel(exif.blackLevels, 0)
    return pyffyCommon.setActiveAreaPixels(image, activeAreaImage, exif.imageHeight, exif.imageWidth, exif.activeArea)


def process(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, referenceExif: PyffyExif, settings: PyffySettings) -> ndarray[uint16]:
    activeAreaImage = pyffyCommon.getActiveAreaPixels(image, exif.imageHeight, exif.imageWidth, exif.activeArea)
    activeAreaImageHeight = activeAreaImage.shape[0]
    activeAreaImageWidth = activeAreaImage.shape[1]
    activeAreaImage = activeAreaImage.reshape((-1))
    activeAreaImage = activeAreaImage.clip(pyffyCommon.getBlackWhiteLevel(exif.blackLevels, 0)) - pyffyCommon.getBlackWhiteLevel(exif.blackLevels, 0)
    activeAreaReference = pyffyCommon.getActiveAreaPixels(reference, referenceExif.imageHeight, referenceExif.imageWidth, exif.activeArea)
    activeAreaReference -= pyffyCommon.getBlackWhiteLevel(referenceExif.blackLevels, 0)

    activeAreaReference = activeAreaReference.astype(float32)
    activeAreaReference = pyffyCommon.blurChannel(activeAreaReference, activeAreaImageHeight, activeAreaImageWidth, settings.advGaussianFilterSigma)
    activeAreaReference = pyffyCommon.scaleChannel(activeAreaReference)

    activeAreaImage = activeAreaImage.astype(float32)
    activeAreaImage = pyffyCommon.correctMonochrome(activeAreaImage, activeAreaReference, settings.luminanceCorrectionIntensity)
    activeAreaImage = pyffyCommon.fitChannelToAllowedRange(activeAreaImage, pyffyCommon.getBlackWhiteLevel(exif.blackLevels, 0), pyffyCommon.getBlackWhiteLevel(exif.whiteLevels, 1), settings.advLimitToWhiteLevels)

    activeAreaImage = activeAreaImage.astype(uint16)
    return pyffyCommon.setActiveAreaPixels(image, activeAreaImage, exif.imageHeight, exif.imageWidth, exif.activeArea)
