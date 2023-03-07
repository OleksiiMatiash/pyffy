import fileNameUtils
import os
import shutil
from pathlib import Path

import numpy as np
from numpy import ndarray

referenceFilesExifDBFileName = "referenceDB.json"
settingsForTwoPassProcessingFileName = "processingSettings.json"


def readImageData(fileName: str, offset: int, length: int) -> ndarray:
    return np.fromfile(fileName, dtype = np.uint16, count = length, offset = offset)


def writeImageData(fileName: str, offset: int, cfa: ndarray):
    with open(fileName, "r+b") as f:
        f.seek(offset)
        f.write(cfa.tobytes())


def getReferenceFilesRootFolderPath(referenceFilesRootFolderPath: str) -> Path | None:
    referenceFolderPath = Path(referenceFilesRootFolderPath).resolve().absolute()
    if referenceFolderPath.exists():
        return referenceFolderPath
    else:
        print("Path to the reference folder root is wrong")
        return None


def readReferenceFilesDB(referenceFilesRootFolderPathStr: str) -> str | None:
    referenceFolderPath = getReferenceFilesRootFolderPath(referenceFilesRootFolderPathStr)
    if referenceFolderPath is None:
        return None

    referenceFilesExifDBFile = "{0}\\{1}".format(str(referenceFolderPath), referenceFilesExifDBFileName)

    if Path(referenceFilesExifDBFile).exists():
        with open(referenceFilesExifDBFile, "r") as f:
            return f.read()
    else:
        return None


def writeReferenceFilesDB(content: str, referenceFilesRootFolderPathStr: str):
    referenceFolderPath = getReferenceFilesRootFolderPath(referenceFilesRootFolderPathStr)
    if referenceFolderPath is None:
        return

    referenceFilesExifDBFile = "{0}\\{1}".format(str(referenceFolderPath), referenceFilesExifDBFileName)
    with open(referenceFilesExifDBFile, "wt") as f:
        f.write(content)


def writeImageSettingsForTwoPassProcessing(path: str, content: str):
    path = Path(path).resolve().joinpath(settingsForTwoPassProcessingFileName)
    with open(path, "wt") as f:
        f.write(content)


def readImageSettingsForTwoPassProcessing(path: str) -> str | None:
    path = Path(path).resolve().joinpath(settingsForTwoPassProcessingFileName)
    if not path.exists():
        return None
    with open(path, "r") as f:
        return f.read()


def getDngFilesInFolder(rootFolder: str) -> list[str]:
    files = [f for f in os.listdir(rootFolder) if os.path.isfile(os.path.join(rootFolder, f)) and str(f).lower().endswith(".dng")]
    result = []
    for fileName in files:
        result.append(str(os.path.join(rootFolder, fileName)))
    return result


def getDngFilesInTree(rootFolder: str) -> list[str]:
    result = []
    for root, dirs, files in os.walk(rootFolder):
        for name in files:
            if name.lower().endswith(".dng"):
                result.append(str(Path(os.path.join(root, name)).resolve()))
    return result


def getRelativePath(rootFolder: str, absolutePath: str) -> str:
    return str(Path(absolutePath).relative_to(Path(rootFolder).resolve()))


def getAbsolutePath(rootFolder: str, relativePath: str) -> str | None:
    try:
        absolutePath = Path(rootFolder).resolve().joinpath(relativePath)
    except:
        absolutePath = None

    if absolutePath is None or not absolutePath.exists():
        return None
    return str(absolutePath)


def writeSettings(settingsString: str):
    print("Writing settings")
    with open("settings.json", "wt") as f:
        f.write(settingsString)


def readSettings() -> str | None:
    print("Reading settings")
    if not Path("settings.json").exists():
        print("Settings file is not found!")
        return None
    with open("settings.json", "r") as f:
        return f.read()


def createTempFile(fileName) -> str:
    return shutil.copyfile(fileName, fileName + ".tmp")


def getDestinationFolder(fileName: str, pathForProcessedFiles: str) -> str | None:
    try:
        outputPath = Path(pathForProcessedFiles)
    except:
        outputPath = None

    if outputPath is not None and not outputPath.is_absolute():
        return str(Path(fileName).parent.joinpath(pathForProcessedFiles))

    return outputPath


def copyFileToDestination(fileName: str, pathForProcessedFiles: str) -> str:
    Path(pathForProcessedFiles).mkdir(parents = True, exist_ok = True)
    return shutil.copy(fileName, pathForProcessedFiles)


def replaceOriginalFileWithTmp(fileName: str, destinationFileName: str, isSend2TrashInstalled: bool):
    if Path(destinationFileName).exists():
        deleteToRecycleIfPossible(fileName, isSend2TrashInstalled)
        shutil.move(destinationFileName, fileName)


def deleteToRecycleIfPossible(fileName: str, isSend2TrashInstalled: bool):
    if isSend2TrashInstalled:
        import send2trash
        send2trash.send2trash(fileName)
    else:
        Path(fileName).unlink(missing_ok = True)


def copyFile(fileName: str, suffix: str) -> str:
    destName = fileNameUtils.getFileName(fileName) + suffix + fileNameUtils.getExtension(fileName)
    shutil.copy(fileName, destName)
    return destName
