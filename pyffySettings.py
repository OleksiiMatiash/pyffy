import json


class PyffySettings:
    def __init__(self, jsonDict: None | dict = None):
        self.useMultithreading: bool = True
        self.referenceFilesRootFolder: str = ""
        self.pathForProcessedFiles: str = ""
        self.overwriteSourceFile: bool = False
        self.askForConfirmationOnStartIfOverwritingOriginalsIsEnabled: bool = True
        self.luminanceCorrectionIntensity: float = 1.0
        self.colorCorrectionIntensity: float = 1.0
        self.advUseFirstFoundReferenceInsteadOfSkippingProcessing: bool = False
        self.advIgnoreLensTag: bool = True
        self.advLimitToWhiteLevels = True
        self.advGaussianFilterSigma: float = 50.0
        self.advMaxAllowedFocalLengthDifferencePercent: float = 5.0
        self.advMaxAllowedFNumberDifferenceStops: float = 0.5
        self.advUpdateDngSoftwareTagToAvoidOverprocessing = True
        self.advOverWriteSourceFileInPlace: bool = False

        if jsonDict is not None:
            [setattr(self, key, val) for key, val in jsonDict.items() if hasattr(self, key)]

    @staticmethod
    def parse(settingsStr: str):
        try:
            return PyffySettings(json.loads(settingsStr))
        except:
            return None

    def serialize(self) -> str | None:
        try:
            return json.dumps(self, indent = 4, default = lambda x: x.__dict__)
        except:
            return None
