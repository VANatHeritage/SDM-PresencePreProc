# wrpAddInitFlds.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-09
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the AddInitFlds function, which adds and populates initial standard data fields need for data review, QC, and editing.

# Usage Notes:
# This should be run after SplitBiotics, and before CullDuplicates. It can be run on either Biotics or non-Biotics data.
# -------------------------------------------------------------------------------------

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The input polygon feature class you want to pre-process
inPolys = r'path\to\input\feature\class'  

# The 8-character species code to be used for modeling
spCode: 'charcode'

# The code for the data source table
srcTab: 'biotics' # or some other source code

# The field (in inPolys) containing the record ID you want to use to identify duplicates
fldID: 'SF_ID' # or some other field name

# The field (in inPolys) containing the observation dates
fldDate: 'OBSDATE' # or some other field name

# The output feature class
outPolys: r'path\to\output\feature\class'

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################


# Import required module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

# Run function
AddInitFlds(inPolys, spCode, srcTab, fldID, fldDate, outPolys)