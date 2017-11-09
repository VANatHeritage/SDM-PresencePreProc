# wrpMergeData.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-09
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the MergeData function, which merges multiple input datasets into one consolidated set with standard fields.

# Usage Notes:
# This should be run after Cull Duplicates, and before SpatialCluster.
# Inputs must all be in the same coordinate system, so make sure that is true before running.
# -------------------------------------------------------------------------------------

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The list of feature classes to merge.  These must be contained within brackets, separated by commas. It is okay to have just one feature class in the list, but it must be in brackets.
inList = [r'path\to\input\feature\class1', r'path\to\input\feature\class2'] 

# The output merged feature class
outPolys = r'path\to\output\feature\class'

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################


# Import required module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

# Run function
MergeData(inList, outPolys)