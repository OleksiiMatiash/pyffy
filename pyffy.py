import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pkg_resources

import pyffyCFA
import pyffyCommon
import pyffyDB
import pyffyExif
import pyffyIO
import pyffyMono
import pyffyRGB
from pyffyExif import PyffyExif
from pyffySettings import PyffySettings


def onePassWithOneReference(processFilesInSubfolders: bool, commonReferenceFile: str):
    print("Pyffy is in one pass with one reference mode.")
    settings = prepareSettings()

    installedPackages = {pkg.key for pkg in pkg_resources.working_set}
    setIdlePriority(installedPackages)
    isSend2TrashInstalled = "send2trash" in installedPackages

    computationExecutor = ThreadPoolExecutor()
    ioExecutor = ThreadPoolExecutor()

    referenceFilePath = commonReferenceFile
    referenceFileExif = pyffyExif.getExif(fileName = referenceFilePath)

    if processFilesInSubfolders:
        dngFiles = pyffyIO.getDngFilesInTree(u".")
    else:
        dngFiles = pyffyIO.getDngFilesInFolder(u".")

    for fileName in dngFiles:
        print("Processing {0}".format(fileName))
        exif = pyffyExif.getExif(fileName)

        if not pyffyExif.isFileAndReferenceCompatible(exif, referenceFileExif):
            continue

        processOneFile(fileName, exif, referenceFilePath, referenceFileExif, settings, computationExecutor, ioExecutor, isSend2TrashInstalled)
        print("")

    computationExecutor.shutdown()
    ioExecutor.shutdown()


def onePass(processFilesInSubfolders: bool, workingPath: str):
    print("Pyffy is in one pass with many references mode.")

    workingPath = workingPath.replace("\"", "").replace("'", "")

    settings = prepareSettings()

    installedPackages = {pkg.key for pkg in pkg_resources.working_set}
    setIdlePriority(installedPackages)
    isSend2TrashInstalled = "send2trash" in installedPackages

    computationExecutor = ThreadPoolExecutor()
    ioExecutor = ThreadPoolExecutor()

    referenceDB = prepareReferenceDB(settings.referenceFilesRootFolder)

    if referenceDB is None or len(referenceDB) == 0:
        exitWithPrompt("Reference files DB is not found or is empty.")

    try:
        workingPath = str(Path(workingPath).resolve())
    except:
        exitWithPrompt("Provided working path is invalid!")

    if processFilesInSubfolders:
        dngFiles = pyffyIO.getDngFilesInTree(workingPath)
    else:
        dngFiles = pyffyIO.getDngFilesInFolder(workingPath)

    for fileName in dngFiles:
        exif = pyffyExif.getExif(fileName)

        if settings is None or len(settings.referenceFilesRootFolder) == 0:
            exitWithPrompt("Please set reference folder path in settings.json.")

        referenceFileRecords = pyffyDB.getReferenceFileRecords(referenceDB, exif, settings)

        if len(referenceFileRecords) == 0:
            print("No applicable reference file found in DB, skipping. It's metadata:")
            print(pyffyCommon.dictToJson(exif))
            continue

        if len(referenceFileRecords) > 1 and not settings.advUseFirstFoundReferenceInsteadOfSkippingProcessing:
            print("More than one applicable reference file is found. Please either delete all but one applicable reference files, use two pass or one reference file mode.")
            print("File that has more than one applicable reference file: {0}".format(fileName))
            print("Applicable reference files:")
            for referenceFileRecord in referenceFileRecords:
                print(pyffyCommon.dictToJson(referenceFileRecord))
            continue

        referenceFilePath, referenceFileExif = referenceFileRecords.popitem()
        referenceFilePath = pyffyIO.getAbsolutePath(settings.referenceFilesRootFolder, referenceFilePath)
        if referenceFilePath is None:
            print("Reference field file record was found in DB, but corresponding file is not present.")
            continue

        processOneFile(fileName, exif, referenceFilePath, referenceFileExif, settings, computationExecutor, ioExecutor, isSend2TrashInstalled)
        print("")

    computationExecutor.shutdown()
    ioExecutor.shutdown()


def twoPasses(processFilesInSubfolders: bool, workingPath: str):
    print("Pyffy is in two pass mode.")

    workingPath = workingPath.replace("\"", "").replace("'", "")

    settings = prepareSettings()

    settingsForTwoPassProcessing = pyffyDB.readSettingsForTwoPassProcessing(pyffyIO.readImageSettingsForTwoPassProcessing(workingPath))
    referenceDB = prepareReferenceDB(settings.referenceFilesRootFolder)

    if processFilesInSubfolders:
        dngFiles = pyffyIO.getDngFilesInTree(workingPath)
    else:
        dngFiles = pyffyIO.getDngFilesInFolder(workingPath)

    if settingsForTwoPassProcessing is None:
        print("Pass one. Creating settings for all DNG files.")

        pyffyIO.writeImageSettingsForTwoPassProcessing(workingPath, pyffyCommon.dictToJson(pyffyDB.createSettingsForTwoPassProcessing(dngFiles, workingPath, referenceDB, settings)))

        exitWithPrompt("Done. Edit {0} and start this script again for second pass.".format(pyffyIO.settingsForTwoPassProcessingFileName))
    else:
        print("Pass two.")

        installedPackages = {pkg.key for pkg in pkg_resources.working_set}
        setIdlePriority(installedPackages)
        isSend2TrashInstalled = "send2trash" in installedPackages

        computationExecutor = ThreadPoolExecutor()
        ioExecutor = ThreadPoolExecutor()

        for fileName in dngFiles:
            relativeFilePath = pyffyIO.getRelativePath(workingPath, fileName)
            settingsForFile = settingsForTwoPassProcessing.get(relativeFilePath)

            if (settingsForFile.referenceFiles is None or
                    len(settingsForFile.referenceFiles) == 0 or
                    len(settingsForFile.referenceFiles) > 1 and not settings.advUseFirstFoundReferenceInsteadOfSkippingProcessing):
                print("Reference files entry must contain exactly one record. Skipping {0}".format(relativeFilePath))
                continue

            referenceFile = settingsForFile.referenceFiles[0]
            referenceFile = pyffyIO.getAbsolutePath(settings.referenceFilesRootFolder, referenceFile)
            referenceFileExif = pyffyExif.getExif(referenceFile)

            processOneFile(fileName, pyffyExif.getExif(fileName), referenceFile, referenceFileExif, settings, computationExecutor, ioExecutor, isSend2TrashInstalled)
            print("")

        computationExecutor.shutdown()
        ioExecutor.shutdown()


def processOneFile(fileName: str,
                   exif: PyffyExif,
                   referenceFilePath: str,
                   referenceFileExif: PyffyExif,
                   settings: PyffySettings,
                   computationExecutor: ThreadPoolExecutor,
                   ioExecutor: ThreadPoolExecutor,
                   isSend2TrashInstalled: bool):
    if settings.advUpdateDngSoftwareTagToAvoidOverprocessing and exif.isFileAlreadyProcessed():
        print("{0} is skipped because advUpdateDngSoftwareTagToAvoidOverprocessing is true in settings.json and tag \"Software\" in dng file already contains \"pyffy\".".format(fileName))
        return

    print("Processing file {0} with reference file {1}".format(fileName, referenceFilePath))
    startTime = time.time()

    imageData = pyffyIO.readImageData(fileName, exif.dataOffset, exif.dataSizeInWords)
    referenceImageData = pyffyIO.readImageData(referenceFilePath, referenceFileExif.dataOffset, referenceFileExif.dataSizeInWords)

    fileCopyFuture = None
    if not settings.advOverWriteSourceFileInPlace:
        if settings.overwriteSourceFile:
            fileCopyFuture = ioExecutor.submit(pyffyIO.createTempFile, fileName)
        else:
            destinationFolder = pyffyIO.getDestinationFolder(fileName, settings.pathForProcessedFiles)
            if destinationFolder is None:
                exitWithPrompt("Path provided in pathForProcessedFiles must be valid!")
            fileCopyFuture = ioExecutor.submit(pyffyIO.copyFileToDestination, fileName, destinationFolder)

    if exif.isFileLinear():
        if exif.isFileMonochrome():
            imageData = pyffyMono.process(imageData, referenceImageData, exif, referenceFileExif, settings)
        else:
            imageData = pyffyRGB.process(imageData, referenceImageData, exif, referenceFileExif, settings, computationExecutor)
    else:
        imageData = pyffyCFA.process(imageData, referenceImageData, exif, referenceFileExif, settings, computationExecutor)

    if fileCopyFuture is None:
        destinationFileName = fileName
    else:
        destinationFileName = fileCopyFuture.result()

    pyffyIO.writeImageData(destinationFileName, exif.dataOffset, imageData)

    if exif.software.count("pyffy") == 0:
        pyffyExif.removeDngChecksum(destinationFileName)

    if settings.advUpdateDngSoftwareTagToAvoidOverprocessing:
        pyffyExif.addPyffyToSoftwareTag(destinationFileName, exif.software)

    if settings.overwriteSourceFile and not settings.advOverWriteSourceFileInPlace:
        pyffyIO.replaceOriginalFileWithTmp(fileName, destinationFileName, isSend2TrashInstalled)

    print("Processed in {0} s".format(time.time() - startTime))


def prepareSettings():
    settingsJson = pyffyIO.readSettings()
    if settingsJson is None:
        pyffyIO.writeSettings(PyffySettings().serialize())
        print("Settings file settings.json was created with default values. Please edit it to set up your reference files folder root.")
        exitWithPrompt()

    settings = PyffySettings.parse(settingsJson)
    if settings is None:
        print("File settings.json was found, but could not be parsed. Please either delete it to create default one, or edit with correct values.")
        exitWithPrompt()

    if len(settings.referenceFilesRootFolder) == 0:
        print("Please set reference folder path in settings.json")
        exitWithPrompt()

    if not settings.overwriteSourceFile and settings.pathForProcessedFiles == "":
        print("overwriteSourceFile is false and pathForProcessedFiles is empty in settings.json. Please either allow overwriting original files, or set the output path.")
        exitWithPrompt()

    if settings.overwriteSourceFile and settings.askForConfirmationOnStartIfOverwritingOriginalsIsEnabled:
        print("Overwriting original files is enabled in settings!")
        input("Press Enter to confirm or close this window to abort.")

    return settings


def prepareReferenceDB(referenceFilesRootFolderStr: str) -> dict[str, PyffyExif] | None:
    print("Reading reference files DB")
    referenceDB = pyffyDB.parseReferenceDB(pyffyIO.readReferenceFilesDB(referenceFilesRootFolderStr))

    if referenceDB is None:
        print("Reference files DB is not found, creating it")
        referenceDB = pyffyDB.createReferenceDB(referenceFilesRootFolderStr)
        pyffyIO.writeReferenceFilesDB(pyffyCommon.dictToJson(referenceDB), referenceFilesRootFolderStr)

    if referenceDB is not None:
        print("referenceDB contains {0} files".format(len(referenceDB)))

    absoluteReferenceDB = dict()
    for key in referenceDB.keys():
        absoluteReferenceDB[pyffyIO.getAbsolutePath(referenceFilesRootFolderStr, key)] = referenceDB[key]

    return absoluteReferenceDB


def setIdlePriority(installedPackages):
    if "psutil" in installedPackages:
        import psutil
        psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)


def exitWithPrompt(message: str | None = None):
    if message is not None:
        print(message)
    input("Press Enter to exit.")
    sys.exit()
