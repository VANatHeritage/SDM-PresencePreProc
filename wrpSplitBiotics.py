# wrpSplitBiotics.py
# Version:  Python 2.7.5
# Creation Date: 2017-11-09
# Last Edit: 2017-11-09
# Creator:  Kirsten Hazler
#
# Summary: 
# Calls the SplitBiotics function, which splits a standard input Biotics dataset into multiple datasets based on element codes

# Usage Notes:
# This should be run before any other processing, if Biotics data are not already split out by species. This script is strictly for use on Biotics data with standard field names.
# -------------------------------------------------------------------------------------

############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

# The input feature class containing Biotics data that you want to split
inFeats = r'path\to\input\feature\class' 

# The input crosswalk file (must be an Excel file)
inXwalk = r'path\to\crosswalk\table'  

# The field in the crosswalk table containing the output code to use for feature class names
# This should not contain any spaces or weird characters!
fldOutCode = 'NameOfField' 

# The file geodatabase to contain the output feature classes
# You must have already created this.
outGDB = r'path\to\geodatabase'  

############################################################################
####################### USER INPUT SECTION ENDS HERE #######################
############################################################################


# Import required module and functions
import sdmPresencePreProc
from sdmPresencePreProc import *

# Run function
SplitBiotics(inFeats, inXwalk, fldOutCode, outGDB)