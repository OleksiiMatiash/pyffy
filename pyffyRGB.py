from concurrent.futures import ThreadPoolExecutor

import numpy as np
from numpy import float32, ndarray, uint16

import pyffyCommon
from pyffyExif import PyffyExif
from pyffySettings import PyffySettings


def bitwiseMask(image: ndarray[uint16], exif: PyffyExif, bits: int, leaveLSB: bool) -> ndarray[uint16]:
    channels = imageToChannels(image, exif.blackLevels)
    channels = pyffyCommon.bitwiseMask(channels, bits, leaveLSB)
    for i in range(channels.shape[0]):
        channels[i] += pyffyCommon.getBlackWhiteLevel(exif.blackLevels, i)
    return channelsToImage(channels)


def process(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, referenceExif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    channels, referenceChannels = imagesToChannels(image, reference, exif.blackLevels, referenceExif.blackLevels, settings.useMultithreading, executor)

    referenceChannels = referenceChannels.astype(float32)
    referenceChannels = pyffyCommon.blurChannels(referenceChannels, exif.imageHeight, exif.imageWidth, settings.advGaussianFilterSigma, settings.useMultithreading, executor)
    referenceChannels = pyffyCommon.normalizeChannels(referenceChannels, settings.useMultithreading, executor)

    channels = channels.astype(float32)
    channels, referenceChannels = pyffyCommon.correctLuminance(channels, referenceChannels, exif.colorPattern, settings.luminanceCorrectionIntensity, settings.useMultithreading, executor)
    channels = pyffyCommon.correctColor(channels, referenceChannels, exif.colorPattern, settings.colorCorrectionIntensity, settings.useMultithreading, executor)
    channels = pyffyCommon.fitChannelsToAllowedRange(channels, exif.blackLevels, exif.whiteLevels, settings.advLimitToWhiteLevels, settings.useMultithreading, executor)

    channels = channels.astype(uint16)
    return channelsToImage(channels)


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
    channels = np.empty((3, np.size(image) // 3), dtype = uint16)
    channels[0] = image[0::3].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 0)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 0)
    channels[1] = image[1::3].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 1)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 1)
    channels[2] = image[2::3].clip(pyffyCommon.getBlackWhiteLevel(blackLevels, 2)) - pyffyCommon.getBlackWhiteLevel(blackLevels, 2)
    return channels


def channelsToImage(channels: ndarray[uint16]) -> ndarray[uint16]:
    channels = np.row_stack(channels)
    return np.reshape(channels, (1, np.size(channels[0]) * 3), "F")


def correctLuminance(channels: ndarray[float32],
                     referenceChannels: ndarray[float32],
                     colorPattern: [int],
                     luminanceCorrectionIntensity: float,
                     useMultithreading: bool,
                     executor: ThreadPoolExecutor) -> (ndarray[float32], ndarray[float32]):
    scaledGreenChannel = referenceChannels[colorPattern.index(1)]
    scaledGreenChannel = scaledGreenChannel / np.max(scaledGreenChannel)

    if useMultithreading:
        futures = dict()
        if luminanceCorrectionIntensity != 0:
            for i in range(len(colorPattern)):
                futures[i] = executor.submit(pyffyCommon.divideChannel, channels[i], scaledGreenChannel, luminanceCorrectionIntensity)
            for i in range(len(futures)):
                channels[i] = futures[i].result()
            futures.clear()

        for i in range(len(colorPattern)):
            if colorPattern[i] != 1:
                futures[i] = executor.submit(pyffyCommon.divideChannel, referenceChannels[i], scaledGreenChannel, luminanceCorrectionIntensity)
        for key in futures.keys():
            referenceChannels[key] = futures[key].result()
    else:
        if luminanceCorrectionIntensity != 0:
            for i in range(len(colorPattern)):
                channels[i] = pyffyCommon.divideChannel(channels[i], scaledGreenChannel, luminanceCorrectionIntensity)

        for i in range(len(colorPattern)):
            if colorPattern[i] != 1:
                referenceChannels[i] = pyffyCommon.divideChannel(referenceChannels[i], scaledGreenChannel, luminanceCorrectionIntensity)
    return channels, referenceChannels
