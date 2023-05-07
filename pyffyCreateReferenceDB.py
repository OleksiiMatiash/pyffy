import sys

import pyffy

if len(sys.argv) == 1:
    pyffy.prepareReferenceDB(u".")
elif len(sys.argv) == 2:
    pyffy.prepareReferenceDB(sys.argv[1])
