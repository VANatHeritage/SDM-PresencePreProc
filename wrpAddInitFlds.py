# wrpAddInitFlds.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-14
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the AddInitFlds function, which adds and populates initial standard data fields need for data review, QC, and editing.

# Usage Notes:
# This should be run after SplitBiotics, and before CullDuplicates. It can be run on either Biotics or non-Biotics data.
# -------------------------------------------------------------------------------------

# Import required module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The input polygon feature class you want to pre-process
inPolys = r'C:\Testing\SpeciesFeatures.gdb\clemaddi'  # replace with your data path

# The 8-character species code to be used for modeling
spCode = 'clemaddi' # or some other species code

# The code for the data source table
srcTab = 'biotics' # or some other source code

# The field (in inPolys) containing the record ID you want to use to identify duplicates
fldID = 'SF_ID' # or some other field name

# The field (in inPolys) containing the observation dates
fldDate = 'OBSDATE' # or some other field name

# The output feature class
outPolys = r'C:\Testing\SpeciesFeatures.gdb\clemaddi_proc'  # replace with your data path

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################

# Run function
AddInitFlds(inPolys, spCode, srcTab, fldID, fldDate, outPolys)
