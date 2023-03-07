import sys

import pyffy

if len(sys.argv) == 1:
    pyffy.twoPasses(processFilesInSubfolders = True, workingPath = u".")
elif len(sys.argv) == 2:
    pyffy.twoPasses(processFilesInSubfolders = True, workingPath = sys.argv[1])
else:
    pyffy.exitWithPrompt("Only one folder can be provided to this script. Exiting now.")
