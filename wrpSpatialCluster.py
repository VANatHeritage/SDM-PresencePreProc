# wrpSpatialCluster.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-09
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the SpatialCluster function, which clusters features based on the specified search distance. Features within twice the search distance of each other will be assigned to the same group.

# Usage Notes:
# This should be run after MergeData.
# The specified search distance should be half of the maximum distance allowed between features in the same cluster. For example if you want features within 500 m of each other to cluster together, enter "250 METERS".
# -------------------------------------------------------------------------------------

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The input features to cluster into groups
inFeats = r'I:\SWAPSPACE\K_Hazler\From_Anne\fromACC.gdb\CEGL3714_merge'

# The field containing unique feature IDs in inFeats
fldID = 'OBJECTID' # or other field that uniquely identifies each feature

# The search distance to use for clustering. The specified search distance should be half of the maximum distance allowed between features in the same cluster. For example if you want features within 500 m of each other to cluster together, enter "250 METERS".
searchDist = '250 METERS'

# The desired name for the output grouping field. 
# This is a new field that will be added to the existing input feature class.
fldGrpID = 'grpID'

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################


# Import required module and functions
import Helper
from Helper import *

# Run function
SpatialCluster (inFeats, fldID, searchDist, fldGrpID)
