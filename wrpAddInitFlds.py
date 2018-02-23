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
inPolys = r'C:\David\scratch\sdmPresencePreProc_testing\isotmede\isotmede.shp'  # replace with your data path

# The output geodatabase (file will have same name as original unless srcTab is set)
outGDB = r'C:\David\scratch\sdmPresencePreProc_testing\isotmede\isotmede.gdb'  

# The 8-12 character species code to be used for modeling (make sure to use the same as exported from any Biotics dataset)
spCode = 'isotmede' # or some other species code

# The field (in inPolys) containing the record ID you want to use to identify duplicates (recommended to use an integer field that indentifies unique features)
fldID = 'ORIG_FID'  # or some other field name (do NOT use FID)

# The field (in inPolys) containing the observation dates
fldDate = 'OBSDATE' # or some other field name

# The code for the data source table
srcTab = '#' # Leave as '#' and it will use the name of the input feature class
# change name here if you wish to use a different name for the dataset (not recommended)

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################

# Run function
AddInitFlds(inPolys, outGDB, spCode, fldID, fldDate, srcTab)
