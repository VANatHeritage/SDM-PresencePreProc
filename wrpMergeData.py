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
# bioticsData = r'C:\Testing\SpeciesFeatures.gdb\clemaddi_proc' # replace with your data path
# otherData = r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb' # replace with your data path, or comment out

# The list of feature classes to merge.  These must be contained within brackets, separated by commas. 
# It is okay to have just one feature class in the list, but it must be in brackets.
inList = [r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb\swp1']#,
         # r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb\tool1',
         #  r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb\isotmedeorig'] # Use this line if the only input is bioticsData
# inList = [bioticsData, otherData] # Uncomment this line and comment out the previous if you have multiple datasets

# The output merged feature class
outPolys = r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb\isotmede_merged' # replace with your data path

# A feature class with the template projection for the merged dataset
spatialRef = r'D:\David\arcmap_wd\isotmede_processingJan2017\sdmPresencePreProc\toolout\toolout.gdb\swp1'

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################

# Run function
MergeData(inList, outPolys, spatialRef)