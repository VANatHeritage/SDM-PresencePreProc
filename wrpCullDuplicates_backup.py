# wrpCullDuplicates.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-09
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

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The input feature class (typically outPolys from the AddInitFlds function)
inPolys = r'path\to\input\feature\class'

# The field containing the standardized ID (you should not have to change this)
fldSrcID = 'src_id'

# The field containing the standardized date (you should not have to change this)
fldDateCalc = 'dateCalc'

# The field identifying duplicates (you should not have to change this)
fldIsDup = 'isDup' 

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################


# Import required module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

# Run function
CullDuplicates(inPolys, fldSrcID, fldDateCalc, fldIsDup)