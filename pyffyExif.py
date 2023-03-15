import json
import subprocess

supportedPhotometricInterpretations = ["Color Filter Array", "Linear Raw"]

pyffyFileCompatibilityFields = {"Compression": "Uncompressed",
                                "BitsPerSample": [16, "16 16 16"],
                                "SamplesPerPixel": [1, 3],
                                "Format": "image/dng",
                                "CFALayout": "Rectangular"}


class PyffyExif:
    def __init__(self, jsonDict: None | dict = None):
        self.cameraMaker: str = ""
        self.cameraModel: str = ""
        self.lens: str = ""
        self.fNumber: float = 0
        self.focalLength: float = 0
        self.imageHeight: int = 0
        self.imageWidth: int = 0
        self.activeArea: [int] = []
        self.blackLevels: [int] = []
        self.whiteLevels: [int] = []
        self.dataOffset: int = 0
        self.dataSizeInWords: int = 0
        self.colorPattern: [int] = []
        self.photometricInterpretation: str = ""
        self.samplesPerPixel: int = 0
        self.software: str = ""

        if jsonDict is not None:
            [setattr(self, key, val) for key, val in jsonDict.items() if hasattr(self, key)]

    def isFileLinear(self):
        return self.photometricInterpretation == "Linear Raw"

    def isFileMonochrome(self):
        return self.isFileLinear() and self.samplesPerPixel == 1

    def isFileAlreadyProcessed(self) -> bool:
        return self.software.count("pyffy") == 1


def getExif(fileName: str = None, exifDict: dict = None) -> PyffyExif | None:
    if fileName is not None:
        cp = subprocess.run(args = "exiftool.exe -j -g1 -b \"{0}\"".format(fileName), capture_output = True, encoding = "utf-8")
        if cp.returncode != 0:
            return None
        exifDict = json.loads(str(cp.stdout))[0]
    elif exifDict is None:
        print("FileName is {0}, exifDict is {1}".format(fileName, exifDict))
        return None
    else:
        raise ValueError("Neither file name nor exifDict are not provided")

    pyffyExif = PyffyExif()
    pyffyExif.cameraMaker = findExifValue(exifDict, "Make")
    pyffyExif.cameraModel = findExifValue(exifDict, "Model")
    pyffyExif.lens = findExifValue(exifDict, "Lens")
    pyffyExif.fNumber = findExifValue(exifDict, "FNumber")
    pyffyExif.focalLength = parseFocalLength(findExifValue(exifDict, "FocalLength"))
    pyffyExif.software = findExifValue(exifDict, "Software")

    cfaExif = None
    # dng can contain many images like previews altogether with CFA image, looking for CFA section
    for exifSubdict in exifDict.values():
        if type(exifSubdict) is not dict:
            continue
        photometricInterpretation = dict(exifSubdict).get("PhotometricInterpretation")
        if photometricInterpretation in supportedPhotometricInterpretations and isFileSupported(exifSubdict):
            cfaExif = exifSubdict
            pyffyExif.photometricInterpretation = photometricInterpretation
            break

    if cfaExif is None:
        print("File does not contain supported raw image.")
        return None

    pyffyExif.imageHeight = cfaExif.get("ImageHeight")
    pyffyExif.imageWidth = cfaExif.get("ImageWidth")

    activeArea = cfaExif.get("ActiveArea")
    if activeArea is not None:
        for activeAreaStr in str(activeArea).split(" "):
            pyffyExif.activeArea.append(int(activeAreaStr))

    try:
        whiteLevel = cfaExif.get("WhiteLevel")
        if whiteLevel is None:
            pyffyExif.whiteLevels.append(65535)
        elif type(whiteLevel) is int:
            pyffyExif.whiteLevels.append(whiteLevel)
        elif type(whiteLevel) is str:
            for whiteLevelStr in str(whiteLevel).split(" "):
                pyffyExif.whiteLevels.append(int(whiteLevelStr))
    except:
        pass

    try:
        blackLevel = cfaExif.get("BlackLevel")
        if blackLevel is None:
            pyffyExif.blackLevels.append(0)
        elif type(blackLevel) is int:
            pyffyExif.blackLevels.append(blackLevel)
        elif type(blackLevel) is str:
            for blackLevelStr in str(blackLevel).split(" "):
                pyffyExif.blackLevels.append(int(blackLevelStr))
    except:
        pass

    stripOffsets = cfaExif.get("StripOffsets")
    if type(stripOffsets) is str:
        pyffyExif.dataOffset = int(stripOffsets.split(" ")[0])
    elif type(stripOffsets) is int:
        pyffyExif.dataOffset = stripOffsets

    stripByteCounts = cfaExif.get("StripByteCounts")
    if type(stripByteCounts) is str:
        stripByteCounts = stripByteCounts.split(" ")
        pyffyExif.dataSizeInWords = 0
        for stripByteCount in stripByteCounts:
            pyffyExif.dataSizeInWords += int(stripByteCount)
    elif type(stripByteCounts) is int:
        pyffyExif.dataSizeInWords = stripByteCounts
    pyffyExif.dataSizeInWords = pyffyExif.dataSizeInWords // 2

    cfaPattern = getExifValue(cfaExif, "CFAPattern2")
    if cfaPattern is not None:  # bayer dng
        for item in cfaPattern.split(" "):
            pyffyExif.colorPattern.append(int(item))

    pyffyExif.samplesPerPixel = getExifValue(cfaExif, "SamplesPerPixel")
    if pyffyExif.photometricInterpretation == "Linear Raw" and pyffyExif.samplesPerPixel == 3:  # linear color dng
        pyffyExif.colorPattern = [0, 1, 2]

    return pyffyExif


def parseFocalLength(focalLengthStr: str) -> float:
    try:
        return float(str(focalLengthStr).removesuffix("mm").strip())
    except:
        return 0


def getExifValue(exifDict: dict, tagName: str) -> str | int | float | None:
    value = exifDict.get(tagName)
    if value is None:
        return None
    elif type(value) is int or type(value) is float:
        return value
    elif type(value) is str:
        return value.strip()


def findExifValue(exifDict: dict, tagName: str) -> str | int | float | None:
    if tagName in exifDict: return exifDict[tagName]
    for value in exifDict.values():
        if isinstance(value, dict):
            a = findExifValue(value, tagName)
            if a is not None: return a
    return None


def removeDngChecksum(fileName: str):
    subprocess.run(args = "exiftool.exe -NewRawImageDigest= -overwrite_original \"{0}\"".format(fileName), capture_output = True)


def addPyffyToSoftwareTag(fileName: str, software: str):
    subprocess.run(args = "exiftool.exe -Software=\"{0}, pyffy\" -overwrite_original \"{1}\"".format(software, fileName), capture_output = True)


def isFileAlreadyProcessed(exif: PyffyExif) -> bool:
    return exif.software.count("pyffy") != 0


def isFileSupported(exifDict: dict) -> bool:
    for key, supportedValues in pyffyFileCompatibilityFields.items():
        exifValue = exifDict.get(key)
        if exifValue is not None and exifValue not in supportedValues:
            print("Supported value for tag {0} is {1}, actual is {2}".format(key, supportedValues, exifValue))
            return False
    return True


def isFileAndReferenceCompatible(exif: PyffyExif, referenceExif: PyffyExif):
    return (exif.cameraMaker == referenceExif.cameraMaker and
            exif.cameraModel == referenceExif.cameraModel and
            exif.imageHeight == referenceExif.imageHeight and
            exif.imageWidth == referenceExif.imageWidth and
            exif.activeArea == referenceExif.activeArea and
            exif.colorPattern == referenceExif.colorPattern and
            exif.dataSizeInWords == referenceExif.dataSizeInWords and
            exif.photometricInterpretation == referenceExif.photometricInterpretation)
