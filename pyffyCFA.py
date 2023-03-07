from concurrent.futures import ThreadPoolExecutor

import numpy as np
from numpy import float32, ndarray, uint16

import pyffyCommon
from pyffyExif import PyffyExif
from pyffySettings import PyffySettings


def bitwiseMask(image: ndarray[uint16], exif: PyffyExif, bits: int, leaveLSB: bool, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    activeAreaImage = pyffyCommon.getActiveAreaPixels(image, exif.imageHeight, exif.imageWidth, exif.activeArea)
    activeAreaImageHeight = activeAreaImage.shape[0]
    activeAreaImageWidth = activeAreaImage.shape[1]
    channels = imageToChannels(activeAreaImage, exif.blackLevels)
    channels = pyffyCommon.bitwiseMask(channels, bits, leaveLSB)
    for i in range(channels.shape[0]):
        channels[i] += pyffyCommon.getBlackWhiteLevel(exif.blackLevels, i)
    activeAreaImage = channelsToImage(channels, activeAreaImageHeight, activeAreaImageWidth, True, executor)
    return pyffyCommon.setActiveAreaPixels(image, activeAreaImage, exif.imageHeight, exif.imageWidth, exif.activeArea)


def process(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, referenceExif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    activeAreaImage = pyffyCommon.getActiveAreaPixels(image, exif.imageHeight, exif.imageWidth, exif.activeArea)
    activeAreaImageHeight = activeAreaImage.shape[0]
    activeAreaImageWidth = activeAreaImage.shape[1]
    activeAreaReference = pyffyCommon.getActiveAreaPixels(reference, referenceExif.imageHeight, referenceExif.imageWidth, exif.activeArea)
    channels, referenceChannels = imagesToChannels(activeAreaImage, activeAreaReference, exif.blackLevels, referenceExif.blackLevels, settings.useMultithreading, executor)

    referenceChannels = referenceChannels.astype(float32)
    referenceChannels = pyffyCommon.blurChannels(referenceChannels, activeAreaImageHeight // 2, activeAreaImageWidth // 2, settings.advGaussianFilterSigma, settings.useMultithreading, executor)
    referenceChannels = pyffyCommon.normalizeChannels(referenceChannels, settings.useMultithreading, executor)

    channels = channels.astype(float32)
    channels, referenceChannels = pyffyCommon.correctLuminance(channels, referenceChannels, exif.colorPattern, settings.luminanceCorrectionIntensity, settings.useMultithreading, executor)
    channels = pyffyCommon.correctColor(channels, referenceChannels, exif.colorPattern, settings.colorCorrectionIntensity, settings.useMultithreading, executor)
    channels = pyffyCommon.fitChannelsToAllowedRange(channels, exif.blackLevels, exif.whiteLevels, settings.advLimitToWhiteLevels, settings.useMultithreading, executor)

    channels = channels.astype(uint16)
    activeAreaImage = channelsToImage(channels, activeAreaImageHeight, activeAreaImageWidth, settings.useMultithreading, executor)
    return pyffyCommon.setActiveAreaPixels(image, activeAreaImage, exif.imageHeight, exif.imageWidth, exif.activeArea)


def imagesToChannels(image: ndarray[uint16], reference: ndarray[uint16], blackLevels: [int], referenceBlackLevels: [int], useMultithreading: bool, executor: ThreadPoolExecutor) -> (ndarray[uint16], ndarray[uint16]):
    if useMultithreading:
        channelsFuture = executor.submit(imageToChannels, image, blackLevels)
        referenceFuture = executor.submit(imageToChannels, reference, referenceBlackLevels)
        return channelsFuture.result(), referenceFuture.result()
    else:
        channels = imageToChannels(image, blackLevels)
        referenceChannels = imageToChannels(reference, referenceBlackLevels)
        return channels, referenceChannels


def imageToChannels(image: ndarray[uint16], blackLevels: [int]) -> ndarray[uint16]:
    r1 = image[::2].reshape((-1))
    r2 = image[1::2].reshape((-1))
    channels = np.empty((4, image.size // 4), dtype = uint16)
    channels[0] = r1[0::2].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 0)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 0)
    channels[1] = r1[1::2].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 1)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 1)
    channels[2] = r2[0::2].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 2)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 2)
    channels[3] = r2[1::2].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 3)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 3)
    return channels


def channelsToImage(channels: ndarray[uint16], height: int, width: int, useMultithreading: bool, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    if useMultithreading:
        f1 = executor.submit(twoChannelsToOne, (channels[0], channels[1]), height, width)
        f2 = executor.submit(twoChannelsToOne, (channels[2], channels[3]), height, width)
        return np.hstack((f1.result(), f2.result())).reshape(height, width)
    else:
        channels01 = twoChannelsToOne((channels[0], channels[1]), height, width)
        channels23 = twoChannelsToOne((channels[2], channels[3]), height, width)
        return np.hstack((channels01, channels23)).reshape(height, width)


def twoChannelsToOne(channels: (ndarray[uint16], ndarray[uint16]), height: int, width: int) -> ndarray[uint16]:
    channels = np.row_stack(channels)
    channels = np.reshape(channels, (1, channels[0].size * 2), "F")
    return np.reshape(channels, (height // 2, width))
