import json

import pyffyCommon
import pyffyExif
import pyffyIO
from pyffyExif import PyffyExif
from pyffySettings import PyffySettings


class SettingsForTwoPassProcessing:
    def __init__(self, jsonDict: None | dict = None):
        self.cameraMaker: str = ""
        self.cameraModel: str = ""
        self.lens: str = ""
        self.fNumber: float = 0
        self.focalLength: float = 0
        self.referenceFiles: [str] = []
        self.luminanceCorrectionIntensity: float = 0.0
        self.colorCorrectionIntensity: float = 1.0
        self.advGaussianFilterSigma: float = 50.0
        self.advLimitToWhiteLevels = True

        if jsonDict is not None:
            [setattr(self, key, val) for key, val in jsonDict.items() if hasattr(self, key)]


def createSettingsForTwoPassProcessing(files: list[str], rootFolder: str, referenceDB: dict[str, PyffyExif], settings: PyffySettings) -> dict[str, SettingsForTwoPassProcessing]:
    processingSettingsDict = dict[str, SettingsForTwoPassProcessing]()

    for fileName in files:
        print(fileName)
        exif = pyffyExif.getExif(fileName = fileName)
        if exif is None or settings.advUpdateDngSoftwareTagToAvoidOverprocessing and pyffyExif.isFileAlreadyProcessed(exif):
            continue

        processingSettingsItem = SettingsForTwoPassProcessing()
        processingSettingsItem.cameraMaker = exif.cameraMaker
        processingSettingsItem.cameraModel = exif.cameraModel
        processingSettingsItem.lens = exif.lens
        processingSettingsItem.fNumber = exif.fNumber
        processingSettingsItem.focalLength = exif.focalLength
        referenceFiles = list(getReferenceFileRecords(referenceDB, exif, settings).keys())
        for i in range(len(referenceFiles)):
            referenceFiles[i] = pyffyIO.getRelativePath(settings.referenceFilesRootFolder, referenceFiles[i])
        processingSettingsItem.referenceFiles = referenceFiles
        processingSettingsItem.luminanceCorrectionIntensity = settings.luminanceCorrectionIntensity
        processingSettingsItem.colorCorrectionIntensity = settings.colorCorrectionIntensity
        processingSettingsItem.advGaussianFilterSigma = settings.advGaussianFilterSigma
        processingSettingsItem.advLimitToWhiteLevels = settings.advLimitToWhiteLevels
        processingSettingsDict[pyffyIO.getRelativePath(rootFolder, fileName)] = processingSettingsItem

    return processingSettingsDict


def readSettingsForTwoPassProcessing(settingsStr: str) -> dict[str, SettingsForTwoPassProcessing] | None:
    if settingsStr is None:
        return None

    settings = dict[str, SettingsForTwoPassProcessing]()
    settingsDict: dict[str, dict] = json.loads(settingsStr)
    for key in settingsDict.keys():
        settings[key] = SettingsForTwoPassProcessing(settingsDict[key])
    return settings


def createReferenceDB(referenceFilesRootFolderStr: str) -> dict[str, PyffyExif]:
    print("Creating referenceDB")

    files = pyffyIO.getDngFilesInTree(referenceFilesRootFolderStr)
    referenceDB = dict()

    for filePath in files:
        print("processing {0}".format(filePath))

        exif = pyffyExif.getExif(filePath)
        if exif is None:
            continue
        referenceDB[pyffyIO.getRelativePath(referenceFilesRootFolderStr, filePath)] = exif

    return referenceDB


def parseReferenceDB(valueString: str | None) -> dict[str, PyffyExif] | None:
    try:
        referenceDB = json.loads(valueString)
    except:
        return None

    for key in referenceDB.keys():
        referenceDB[key] = PyffyExif(referenceDB[key])
    return referenceDB


def getReferenceFileRecords(referenceDB: dict[str, PyffyExif], exif: PyffyExif, settings: PyffySettings) -> dict[str, pyffyExif.PyffyExif]:
    referenceDB = filterByCameraMaker(referenceDB, exif)
    referenceDB = filterByCameraModel(referenceDB, exif)
    referenceDB = filterByLens(referenceDB, exif, settings)
    referenceDB = filterByImageDimensions(referenceDB, exif)
    referenceDB = filterByPhotometricInterpretation(referenceDB, exif)
    referenceDB = filterBySamplesPerPixel(referenceDB, exif)
    strictExifDB = filterByFocalLengthStrict(referenceDB, exif)

    if len(strictExifDB) == 0:
        referenceDB = filterByFocalLengthFuzzy(referenceDB, exif, settings.advMaxAllowedFocalLengthDifferencePercent)
    else:
        referenceDB = strictExifDB

    strictExifDB = filterByFNumberStrict(referenceDB, exif)

    if strictExifDB == 0:
        referenceDB = filterByFocalLengthFuzzy(referenceDB, exif, settings.advMaxAllowedFNumberDifferenceStops)
    else:
        referenceDB = strictExifDB

    return referenceDB


def filterByCameraMaker(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        if value.cameraMaker == exif.cameraMaker:
            result[key] = value
    return result


def filterByCameraModel(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        if value.cameraModel == exif.cameraModel:
            result[key] = value
    return result


def filterByLens(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif, settings: PyffySettings) -> dict[str, pyffyExif.PyffyExif]:
    if settings.advIgnoreLensTag:
        return referenceDB
    result = {}
    for key, value in referenceDB.items():
        if value.lens == exif.lens:
            result[key] = value
    return result


def filterByImageDimensions(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        if value.imageHeight == exif.imageHeight and value.imageWidth == exif.imageWidth:
            result[key] = value
    return result


def filterByFocalLengthStrict(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        if value.focalLength == exif.focalLength:
            result[key] = value
    return result


def filterByFocalLengthFuzzy(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif, maxAllowedDifferenceInPercent: float) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        if (value.focalLength - value.focalLength * maxAllowedDifferenceInPercent) <= exif.focalLength <= (value.focalLength + value.focalLength * maxAllowedDifferenceInPercent):
            result[key] = value
    return result


def filterByFNumberStrict(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        if value.fNumber == exif.fNumber:
            result[key] = value
    return result


def filterByFNumberFuzzy(referenceDB: dict[str, pyffyExif.PyffyExif], exif: pyffyExif.PyffyExif, maxAllowedDifferenceInStops: float) -> dict[str, pyffyExif.PyffyExif]:
    result = {}
    for key, value in referenceDB.items():
        fNumberDifferenceInEV = pyffyCommon.calculateEVDifference(value.fNumber, exif.fNumber)
        if fNumberDifferenceInEV <= maxAllowedDifferenceInStops:
            result[key] = value
    return result


def filterByPhotometricInterpretation(referenceDB, exif):
    result = {}
    for key, value in referenceDB.items():
        if value.photometricInterpretation == exif.photometricInterpretation:
            result[key] = value
    return result


def filterBySamplesPerPixel(referenceDB, exif):
    result = {}
    for key, value in referenceDB.items():
        if value.samplesPerPixel == exif.samplesPerPixel:
            result[key] = value
    return result


def assertValue(valueName: str, exifValue: int | float | str, supportedValue: int | float | str) -> bool:
    if type(exifValue) != type(supportedValue):
        print("Error in value {0}: type of exif value is {1}, supported value is {2}".format(valueName, type(exifValue), type(supportedValue)))
        return False
    if exifValue != supportedValue:
        print("Error in value {0}: expected value is {1}, actual value is {2}".format(valueName, supportedValue, exifValue))
        return False
    return True


def updateWithTwoPassSettings(settings: PyffySettings, twoPassFileSettings: SettingsForTwoPassProcessing) -> PyffySettings:
    settings.luminanceCorrectionIntensity = twoPassFileSettings.luminanceCorrectionIntensity
    settings.colorCorrectionIntensity = twoPassFileSettings.colorCorrectionIntensity
    settings.advGaussianFilterSigma = twoPassFileSettings.advGaussianFilterSigma
    settings.advLimitToWhiteLevels = twoPassFileSettings.advLimitToWhiteLevels
    return settings
