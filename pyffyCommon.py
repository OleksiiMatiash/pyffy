import json
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from numpy import float32, ndarray, uint16


def correctLuminance(channels: ndarray[float32],
                     referenceChannels: ndarray[float32],
                     colorPattern: [int],
                     luminanceCorrectionIntensity: float,
                     useMultithreading: bool,
                     executor: ThreadPoolExecutor) -> (ndarray[float32], ndarray[float32]):
    averagedGreenReferenceChannels = None
    greenChannelsCount = 0
    for i in range(channels.shape[0]):
        if colorPattern[i] == 1:
            greenChannelsCount += 1
            if averagedGreenReferenceChannels is None:
                averagedGreenReferenceChannels = np.copy(referenceChannels[i])
            else:
                averagedGreenReferenceChannels += referenceChannels[i]

    averagedGreenReferenceChannels = averagedGreenReferenceChannels / greenChannelsCount

    if useMultithreading:
        futures = dict()
        if luminanceCorrectionIntensity != 0:
            for i in range(channels.shape[0]):
                futures[i] = executor.submit(divideChannel, channels[i], averagedGreenReferenceChannels, luminanceCorrectionIntensity)
            for i in range(len(futures)):
                channels[i] = futures[i].result()
            futures.clear()

        for i in range(channels.shape[0]):
            if colorPattern[i] != 1:
                futures[i] = executor.submit(divideChannel, referenceChannels[i], averagedGreenReferenceChannels)
        for key in futures.keys():
            referenceChannels[key] = futures[key].result()
    else:
        if luminanceCorrectionIntensity != 0:
            for i in range(channels.shape[0]):
                channels[i] = divideChannel(channels[i], averagedGreenReferenceChannels, luminanceCorrectionIntensity)

        for i in range(channels.shape[0]):
            if colorPattern[i] != 1:
                referenceChannels[i] = divideChannel(referenceChannels[i], averagedGreenReferenceChannels)
    return channels, referenceChannels


def correctColor(channels: ndarray[float32], referenceChannels: ndarray[float32], colorPattern: [], correctionIntensity: float, useMultithreading: bool = False, executor: ThreadPoolExecutor = None) -> ndarray[float32]:
    if correctionIntensity == 0:
        return channels

    if useMultithreading:
        futures = dict()
        for i in range(channels.shape[0]):
            if colorPattern[i] != 1:
                futures[i] = executor.submit(divideChannel, channels[i], referenceChannels[i], correctionIntensity)
        for key in futures.keys():
            channels[key] = futures[key].result()
    else:
        for i in range(channels.shape[0]):
            if colorPattern[i] != 1:
                channels[i] = divideChannel(channels[i], referenceChannels[i], correctionIntensity)
    return channels


def correctMonochrome(image: ndarray[float32], reference: ndarray[float32], luminanceCorrectionIntensity: float) -> ndarray[float32]:
    return divideChannel(image, reference / np.max(reference), luminanceCorrectionIntensity)


def divideChannel(channel: ndarray[float32], reference: ndarray[float32], intensity: float = 1.0) -> ndarray[float32]:
    if intensity == 0:
        return channel
    if intensity == 1:
        return np.divide(channel, reference, out = np.zeros_like(channel, dtype = float32), where = reference != 0)
    else:
        return np.divide(channel, 1 - (1 - reference * intensity), out = np.zeros_like(channel, dtype = float32), where = reference != 0)


def fitChannelsToAllowedRange(channels: ndarray[float32], blackLevels: [int], whiteLevels: [int], limitToWhiteLevel: bool, useMultithreading: bool, executor: ThreadPoolExecutor) -> ndarray[float32]:
    if useMultithreading:
        futures = list()
        for i in range(channels.shape[0]):
            futures.append(executor.submit(fitChannelToAllowedRange, channels[i], getBlackWhiteLevel(blackLevels, i), getBlackWhiteLevel(whiteLevels, i), limitToWhiteLevel))
        for i in range(channels.shape[0]):
            channels[i] = futures[i].result()
    else:
        for i in range(channels.shape[0]):
            channels[i] = fitChannelToAllowedRange(channels[i], getBlackWhiteLevel(blackLevels, i), getBlackWhiteLevel(whiteLevels, i), limitToWhiteLevel)

    return channels


def fitChannelToAllowedRange(channel: ndarray[float32], blackLevel: int, whiteLevel: int, limitToWhiteLevel: bool) -> ndarray[float32]:
    channel += blackLevel

    if not limitToWhiteLevel:
        whiteLevel = 65535

    channel = np.clip(channel, a_min = 0, a_max = whiteLevel)

    return channel


def blurChannels(channels: ndarray[float32], height: int, width: int, gaussianFilterSigma: float, useMultithreading: bool, executor: ThreadPoolExecutor) -> ndarray[float32]:
    if useMultithreading:
        futures = []
        for i in range(channels.shape[0]):
            futures.append(executor.submit(blurChannel, channels[i], height, width, gaussianFilterSigma))
        result = np.empty_like(channels, dtype = float32)
        for i in range(channels.shape[0]):
            result[i] = futures[i].result()
    else:
        result = np.empty_like(channels, dtype = float32)
        for i in range(channels.shape[0]):
            result[i] = blurChannel(channels[i], height, width, gaussianFilterSigma)
    return result


def blurChannel(channel: ndarray[float32], height: int, width: int, gaussianFilterSigma: float) -> ndarray[float32]:
    channel = channel.reshape(height, width)
    channel = cv2.GaussianBlur(channel, (0, 0), gaussianFilterSigma, gaussianFilterSigma)
    return channel.reshape(-1)


def normalizeChannels(channels: ndarray[float32], useMultithreading: bool, executor: ThreadPoolExecutor) -> ndarray[float32]:
    if useMultithreading:
        futures = []
        for i in range(channels.shape[0]):
            futures.append(executor.submit(scaleChannel, channels[i]))
        result = np.empty_like(channels, dtype = float32)
        for i in range(channels.shape[0]):
            result[i] = futures[i].result()
    else:
        result = np.empty_like(channels, dtype = float32)
        for i in range(channels.shape[0]):
            result[i] = scaleChannel(channels[i])
    return result


def scaleChannel(channel: ndarray[float32]) -> ndarray[float32]:
    return channel / np.max(channel)


def calculateEVDifference(value1: float, value2: float) -> float:
    return np.fabs(np.round(np.log10(np.pow(value1 / value2, 2)) / np.log10(2)))


def dictToJson(content) -> str:
    return json.dumps(content, indent = 4, default = lambda x: x.__dict__)


def subtractBlack(channels: ndarray[float32], blackLevels: [int]) -> ndarray[float32]:
    for i in range(channels.shape[0]):
        blackLevel = getBlackWhiteLevel(blackLevels, i)
        if blackLevel != 0:
            channels[i] -= blackLevel
    return channels


def addBlack(channels: ndarray[float32], blackLevels: [int]) -> ndarray[float32]:
    for i in range(channels.shape[0]):
        blackLevel = getBlackWhiteLevel(blackLevels, i)
        if blackLevel != 0:
            channels[i] += blackLevel
    return channels


def getActiveAreaPixels(image: ndarray[uint16], height: int, width: int, activeArea: [int]) -> ndarray[uint16]:
    return image.reshape(height, width)[activeArea[0]:activeArea[2], activeArea[1]:activeArea[3]]


def setActiveAreaPixels(image: ndarray[float32], activeAreaImage: ndarray[float32], height: int, width: int, activeArea: [int]) -> ndarray[float32]:
    image = image.reshape(height, width)
    activeAreaImage = activeAreaImage.reshape(activeArea[2] - activeArea[0], activeArea[3] - activeArea[1])
    image[activeArea[0]:activeArea[2], activeArea[1]:activeArea[3]] = activeAreaImage
    return image.reshape(-1)


def getBlackWhiteLevel(levels: [int], channelIndex: int) -> int:
    if len(levels) == 0:
        return 0
    if len(levels) == 1:
        return levels[0]
    else:
        return levels[channelIndex]


def getMinBlackWhiteLevel(levels: [int]) -> int:
    if len(levels) == 0:
        return 0
    else:
        return np.min(levels)


def getMaxBlackWhiteLevel(levels: [int]) -> int:
    if len(levels) == 0:
        return 0
    else:
        return np.max(levels)


def bitwiseMask(data: ndarray[uint16], bits: int, leaveLSB: bool) -> ndarray[uint16]:
    mask = uint16(0xffff)
    if bits > 16:
        bits = 16
    elif bits < 0:
        bits = 0

    if leaveLSB:
        mask ^= uint16(mask << bits)
    else:
        mask &= uint16(mask << 16 - bits)

    data &= mask

    if leaveLSB:
        data = data << 16 - bits

    return data
