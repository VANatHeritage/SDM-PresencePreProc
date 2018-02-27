# wrpCullDuplicates.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-14
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the CullDuplicates function, which removes duplicate records where possible. It marks records for review by setting the value for the 'isDup' field as follows:
#      0 = no duplicates
#      1 = duplicates present
#      2 = duplicates removed

# Usage Notes:
# This should be run after AddInitFlds, and before MergeData.
# -------------------------------------------------------------------------------------

# Import Helper module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The input feature class (typically outPolys from the AddInitFlds function)
inPolys = r'C:\David\scratch\sdmPresencePreProc_testing\isotmede\isotmede.gdb\isotmede_merged' # replace with your data path

# The field containing the standardized ID (you should not have to change this)
fldSrcID = 'src_id'

# The field containing the standardized date (you should not have to change this)
fldDateCalc = 'dateCalc'

# The field identifying duplicates (you should not have to change this)
fldIsDup = 'isDup' 

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################

# Run function
CullDuplicates(inPolys, fldSrcID, fldDateCalc, fldIsDup)