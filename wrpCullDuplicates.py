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
inPolys = r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb\isotmedeorig' # replace with your data path

# The field containing the standardized ID (you should not have to change this)
SrcID_field = 'src_id'

# The field containing the standardized date (you should not have to change this)
DateCalc_field = 'dateCalc'

# The field identifying duplicates (you should not have to change this)
IsDup_field = 'isDup' 

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################

# Run function
CullDuplicates(inPolys, SrcID_field, DateCalc_field, IsDup_field)
