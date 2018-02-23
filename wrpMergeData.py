# wrpMergeData.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-14
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the MergeData function, which merges multiple input datasets into one consolidated set with standard fields.

# Usage Notes:
# This should be run after Cull Duplicates, and before SpatialCluster.
# You should check the post-cull data and if necessary, remove any remaining duplicates before running MergeData.
# Inputs must all be in the same coordinate system, so make sure that is true before running.
# -------------------------------------------------------------------------------------

# Import required module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# Input data
# Working geodatabase, and optionally where to get input data from. Default (if inList is '#') is to take all feature classes from here and merge them.
inGDB = 'C:\David\scratch\sdmPresencePreProc_testing\isotmede\isotmede.gdb'

# The output merged feature class
outPolys = r'C:\David\scratch\sdmPresencePreProc_testing\isotmede\isotmede.gdb\isotmede_merged' # replace with your data path

# The list of feature classes to merge. These must be contained within brackets, separated by commas.
# It is okay to have just one feature class in the list, but it must be in brackets.
# You can leave it as default ("#"), and all feature classes from inGDB will be merged.
inList = "#"
# inList = ['SWP_buff','ISOMEDdiversity_buff','isotmede']

# A feature class with the template projection for the merged dataset
spatialRef = r'C:\David\scratch\sdmPresencePreProc_testing\isotmede\isotmede.gdb\SWP_buff'

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################

# Run function
MergeData(inGDB, outPolys, inList, spatialRef)
