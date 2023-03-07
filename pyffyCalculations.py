from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from numpy import ndarray, uint16, float64

from pyffyExif import PyffyExif
from pyffySettings import PyffySettings


def splitImageToChannels(image: ndarray[uint16], referenceImage: ndarray[uint16], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> (ndarray[float64], ndarray[float64]):
    if settings.useMultithreading:
        channelsFuture = executor.submit(splitBayerToChannels, image, exif)
        referenceFuture = executor.submit(splitBayerToChannels, referenceImage, exif)
        return channelsFuture.result(), referenceFuture.result()
    else:
        channels = splitBayerToChannels(image, exif)
        referenceChannels = splitBayerToChannels(referenceImage, exif)
        return channels, referenceChannels


def splitBayerToChannels(image: ndarray[uint16], exif: PyffyExif) -> ndarray[float64]:
    image = np.reshape(image, (exif.imageHeight, exif.imageWidth))
    r1 = image[::2].reshape((-1))
    r2 = image[1::2].reshape((-1))
    channels = np.empty((4, image.size // 4), dtype = float64)
    channels[0] = float64(r1[::2])
    channels[1] = float64(r1[1::2])
    channels[2] = float64(r2[::2])
    channels[3] = float64(r2[1::2])
    return channels

def splitRGBToChannels(image: ndarray[uint16], exif: PyffyExif) -> ndarray[float64]:



def assembleChannelsToBayer(channels: ndarray[uint16], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    print("Assembling channels to bayer")
    if settings.useMultithreading:
        f1 = executor.submit(assembleTwoChannelsInOne, (channels[0], channels[1]), exif)
        f2 = executor.submit(assembleTwoChannelsInOne, (channels[2], channels[3]), exif)
        return np.hstack((f1.result(), f2.result()))
    else:
        channels01 = assembleTwoChannelsInOne((channels[0], channels[1]), exif)
        channels23 = assembleTwoChannelsInOne((channels[2], channels[3]), exif)
        return np.hstack((channels01, channels23))


def assembleTwoChannelsInOne(channels: (ndarray[uint16], ndarray[uint16]), exif: PyffyExif) -> ndarray[uint16]:
    if exif.isFileLinear():
        return channels
    return np.reshape(np.reshape(np.row_stack(channels), (1, channels[0].size * 2), "F"), (exif.imageHeight // 2, exif.imageWidth))


def process(imageData: ndarray[uint16], referenceData: ndarray[uint16], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    if exif.isFileLinear():
        if exif.isFileMonochrome():
            return processMonochrome(imageData, referenceData, exif, settings)
        else:
            return processLinearRGB(imageData, referenceData, exif, settings)
    else:
        return processBayer(imageData, referenceData, exif, settings, executor)


def processMonochrome(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, settings: PyffySettings) -> ndarray[uint16]:
    image = float64(image)
    reference = float64(reference)
    reference = blurChannel(reference, exif.imageHeight, exif.imageWidth, settings)
    reference = scaleImage(reference, exif.imageHeight, exif.imageWidth, settings)
    image = correctMonochrome(image, reference, settings)
    image = limitImage(image, exif, settings)
    return uint16(image)


def processLinearRGB(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, settings: PyffySettings) -> ndarray[uint16]:


def processBayer(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    channels, referenceChannels = splitImageToChannels(image, reference, exif, settings, executor)
    referenceChannels = blurBayerChannels(referenceChannels, exif, settings, executor)
    referenceChannels = scaleChannels(referenceChannels, exif, settings, executor)
    channels, referenceChannels = correctLuminance(channels, referenceChannels, exif, settings, executor)
    channels = correctColor(channels, referenceChannels, exif, settings, executor)
    channels = limitChannels(channels, exif, settings, executor)
    return assembleChannelsToBayer(channels, exif, settings, executor)


def processBayerDebug(image: ndarray[uint16], reference: ndarray[uint16], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> (ndarray[uint16], ndarray[uint16]):
    channels, referenceChannels = splitImageToChannels(image, reference, exif, settings, executor)
    referenceChannels = blurBayerChannels(referenceChannels, exif, settings, executor)
    referenceChannels = scaleChannels(referenceChannels, exif, settings, executor)
    channels, referenceChannels = correctLuminance(channels, referenceChannels, exif, settings, executor)
    channels = correctColor(channels, referenceChannels, exif, settings, executor)
    channels = limitChannels(channels, exif, settings, executor)
    return blurBayerChannels(splitBayerToChannels(image, exif), exif, settings, executor), channels, uint16(referenceChannels * 65535)


def correctLuminance(channels: ndarray[float64], referenceChannels: ndarray[float64], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> (ndarray[float64], ndarray[float64]):
    print("Correcting luminance")

    averagedGreenReferenceChannels = None
    for i in range(len(exif.cfaPattern)):
        if exif.cfaPattern[i] == 1:
            if averagedGreenReferenceChannels is None:
                averagedGreenReferenceChannels = channels[i]
            else:
                averagedGreenReferenceChannels += channels[i]

    if exif.cfaPattern.count(1) == 2:  # CFA
        averagedGreenReferenceChannels = None
        for i in range(len(exif.cfaPattern)):
            if exif.cfaPattern[i] == 1:
                if averagedGreenReferenceChannels is None:
                    averagedGreenReferenceChannels = channels[i]
                else:
                    averagedGreenReferenceChannels += channels[i]
        averagedGreenReferenceChannels = averagedGreenReferenceChannels / 2
    else:  # linear RGB or monochrome
        averagedGreenReferenceChannels = channels[exif.cfaPattern.index(1)]

    averagedGreenReferenceChannels = averagedGreenReferenceChannels / np.max(averagedGreenReferenceChannels)

    if settings.useMultithreading:
        futures = dict()
        if settings.correctLuminance:
            for i in range(len(exif.cfaPattern)):
                futures[i] = executor.submit(divideImage, channels[i], averagedGreenReferenceChannels, settings.advLuminanceCorrectionIntensity)
            for i in range(len(futures)):
                channels[i] = futures[i].result()
            futures.clear()

        for i in range(len(exif.cfaPattern)):
            if exif.cfaPattern[i] != 1:
                futures[i] = executor.submit(divideImage, referenceChannels[i], averagedGreenReferenceChannels, settings.advLuminanceCorrectionIntensity)
        for key in futures.keys():
            referenceChannels[key] = futures[key].result()
    else:
        if settings.correctLuminance:
            for i in range(len(exif.cfaPattern)):
                channels[i] = divideImage(channels[i], averagedGreenReferenceChannels, settings.advLuminanceCorrectionIntensity)

        for i in range(len(exif.cfaPattern)):
            if exif.cfaPattern[i] != 1:
                referenceChannels[i] = divideImage(referenceChannels[i], averagedGreenReferenceChannels, settings.advLuminanceCorrectionIntensity)
    return channels, referenceChannels


def correctColor(channels: ndarray[float64], referenceChannels: ndarray[float64], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[float64]:
    print("Correcting color")
    if not correctColor:
        return channels

    if settings.useMultithreading:
        futures = dict()
        for i in range(len(exif.cfaPattern)):
            if exif.cfaPattern[i] != 1:
                futures[i] = executor.submit(divideImage, channels[i], referenceChannels[i], settings.advColorCorrectionIntensity)
        for key in futures.keys():
            channels[key] = futures[key].result()
    else:
        for i in range(len(exif.cfaPattern)):
            if exif.cfaPattern[i] != 1:
                channels[i] = divideImage(channels[i], referenceChannels[i], settings.advColorCorrectionIntensity)
    return channels


def correctMonochrome(image: ndarray[uint16], reference: ndarray[uint16], settings: PyffySettings) -> ndarray[float64]:
    print("Correcting monochrome image")
    return divideImage(image, reference / np.max(reference), settings.advLuminanceCorrectionIntensity)


def divideImage(image: ndarray[float64], reference: ndarray[float64], intensity: float) -> ndarray[float64]:
    if intensity == 0:
        return image
    if intensity == 1:
        return np.divide(image, reference, out = np.zeros_like(image, dtype = float64), where = reference != 0)
    else:
        return np.divide(image, 1 - (1 - reference * intensity), out = np.zeros_like(image, dtype = float64), where = reference != 0)


def limitChannels(channels: ndarray[float64], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[uint16]:
    print("Limiting channels to the white level")
    if settings.advScaleInsteadOfClipping:
        channelMaximums = []
        if settings.useMultithreading:
            futures = list()
            for i in range(np.size(channels, 0)):
                futures.append(executor.submit(np.max, channels[i]))
            for i in range(np.size(channels, 0)):
                channelMaximums.append(futures[i].result())
        else:
            for i in range(np.size(channels, 0)):
                channelMaximums.append(np.max(channels[i]))
        commonMaximum = np.max(channelMaximums)

        if commonMaximum <= exif.whiteLevels:
            return uint16(channels)

        scaleMultiplier = exif.whiteLevels / commonMaximum
        if settings.useMultithreading:
            futures = list()
            for i in range(np.size(channels, 0)):
                futures.append(executor.submit(limitImage, channels[i], exif.whiteLevels, settings, scaleMultiplier))
            for i in range(np.size(channels, 0)):
                channels[i] = futures[i].result()
        else:
            for i in range(np.size(channels, 0)):
                channels[i] = limitImage(channels[i], exif, settings, scaleMultiplier)
    else:
        if settings.useMultithreading:
            futures = list()
            for i in range(np.size(channels, 0)):
                futures.append(executor.submit(limitImage, channels[i], exif, settings))
            for i in range(np.size(channels, 0)):
                channels[i] = futures[i].result()
        else:
            for i in range(np.size(channels, 0)):
                channels[i] = limitImage(channels[i], exif, settings)

    return uint16(channels)


def limitImage(image: ndarray[float64], exif: PyffyExif, settings: PyffySettings, scaleMultiplier: float = 1.0) -> ndarray[float64]:
    if settings.advScaleInsteadOfClipping:
        return image * scaleMultiplier
    else:
        return np.clip(image, a_min = 0, a_max = exif.whiteLevels)


def getMaxMean(image: ndarray[float64], imageHeight: int, imageWidth: int, settings: PyffySettings) -> float64:
    image = np.reshape(image, (imageHeight // 2, imageWidth // 2))
    if settings.advSearchForRealVignettingMinimum:
        return float64(np.mean(getCropWithMaxMean(image, settings)))
    else:
        return float64(np.mean(getCenterCrop(image, settings)))


def getCenterCrop(image: ndarray[float64], settings: PyffySettings) -> ndarray[float64]:
    imageCenterX = np.shape(image)[0] // 2
    imageCenterY = np.shape(image)[1] // 2
    halfSampleSideLength = settings.advSearchForVignettingMinimumWindowSidePx // 2
    return image[imageCenterY - halfSampleSideLength: imageCenterY + halfSampleSideLength, imageCenterX - halfSampleSideLength: imageCenterX + halfSampleSideLength]


def getCropWithMaxMean(image: ndarray[float64], settings: PyffySettings) -> ndarray[float64]:
    doubledSampleSideLength = settings.advSearchForVignettingMinimumWindowSidePx * 2
    shape = image.shape
    while shape[0] >= doubledSampleSideLength or shape[1] >= doubledSampleSideLength:
        if shape[0] < doubledSampleSideLength:
            halfArrays = np.array_split(image, 2, 1)
        elif shape[1] < doubledSampleSideLength:
            halfArrays = np.array_split(image, 2, 0)
        elif shape[0] > shape[1]:
            halfArrays = np.array_split(image, 2, 0)
        else:
            halfArrays = np.array_split(image, 2, 1)

        if np.mean(halfArrays[0]) > np.mean(halfArrays[1]):
            image = halfArrays[0]
        else:
            image = halfArrays[1]
        shape = image.shape
    return getCenterCrop(image, settings)


def blurBayerChannels(channels: ndarray[float64], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[float64]:
    print("Blurring reference channels")
    if settings.useMultithreading:
        futures = []
        for i in range(np.shape(channels)[0]):
            futures.append(executor.submit(blurChannel, channels[i], exif.imageHeight // 2, exif.imageWidth // 2, settings))
        result = np.empty_like(channels, dtype = float64)
        for i in range(np.shape(channels)[0]):
            result[i] = futures[i].result()
    else:
        result = np.empty_like(channels, dtype = float64)
        for i in range(np.shape(channels)[0]):
            result[i] = blurChannel(channels[i], exif.imageHeight // 2, exif.imageWidth // 2, settings)
    return result

def blurLinearRawChannels(channels: ndarray[float64], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[float64]:
    print("Blurring reference channels")

def blurChannel(image: ndarray[float64], imageHeight: int, imageWidth: int, settings: PyffySettings) -> ndarray[float64]:
    image = np.reshape(image, (imageHeight, imageWidth))
    if settings.removeDust:
        image = cv2.GaussianBlur(image, (0, 0), settings.advGaussianFilterSigmaForDust, settings.advGaussianFilterSigmaForDust)
    else:
        image = cv2.GaussianBlur(image, (0, 0), settings.advGaussianFilterSigmaForNoise, settings.advGaussianFilterSigmaForNoise)
    return np.reshape(image, -1)


def scaleChannels(channels: ndarray[float64], exif: PyffyExif, settings: PyffySettings, executor: ThreadPoolExecutor) -> ndarray[float64]:
    print("Scaling reference channels")
    if settings.useMultithreading:
        futures = []
        for i in range(np.shape(channels)[0]):
            futures.append(executor.submit(scaleImage, channels[i], exif.imageHeight // 2, exif.imageWidth // 2, settings))
        result = np.empty_like(channels, dtype = float64)
        for i in range(np.shape(channels)[0]):
            result[i] = futures[i].result()
    else:
        result = np.empty_like(channels, dtype = float64)
        for i in range(np.shape(channels)[0]):
            result[i] = scaleImage(channels[i], exif.imageHeight // 2, exif.imageWidth // 2, settings)
    return result


def scaleImage(image: ndarray[float64], imageHeight: int, imageWidth: int, settings: PyffySettings) -> ndarray[float64]:
    image = np.reshape(image, -1)
    if settings.advUseWindowAveragingToFindVignettingMinimum:
        mean = getMaxMean(image, imageHeight, imageWidth, settings)
        if mean == 0:
            return np.zeros_like(image)
        return image / mean
    else:
        return image / np.max(image)


def calculateEVDifference(value1: float, value2: float) -> float:
    return np.fabs(np.round(np.log10(np.pow(value1 / value2, 2)) / np.log10(2)))


def showChannel(channel: ndarray[float64], imageHeight: int, imageWidth: int, windowTitle: str):
    r = 900 / float(imageHeight // 2)
    dim = (int(imageWidth // 2 * r), 900)
    cv2.imshow(windowTitle, cv2.resize(channel, dim, interpolation = cv2.INTER_AREA))
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def showChannels(channels: ndarray[float64], imageHeight: int, imageWidth: int, windowTitle: str):
    channel0 = np.uint8(np.reshape(channels[0] * 255 / np.max(channels[0]), (imageHeight // 2, imageWidth // 2)))
    channel1 = np.uint8(np.reshape(channels[1] * 255 / np.max(channels[1]), (imageHeight // 2, imageWidth // 2)))
    channel2 = np.uint8(np.reshape(channels[2] * 255 / np.max(channels[2]), (imageHeight // 2, imageWidth // 2)))
    channel3 = np.uint8(np.reshape(channels[3] * 255 / np.max(channels[3]), (imageHeight // 2, imageWidth // 2)))

    h1 = np.concatenate((channel0, channel1), axis = 1)
    h2 = np.concatenate((channel2, channel3), axis = 1)
    image = np.concatenate((h1, h2), axis = 0)

    dim = None
    (h, w) = image.shape[:2]

    # if width is None:
    r = 1200 / float(h)
    dim = (int(w * r), 1200)
    # else:
    # r = 1600 / float(w)
    # dim = (1600, int(h * r))

    cv2.imshow(windowTitle, cv2.resize(image, dim, interpolation = cv2.INTER_AREA))
