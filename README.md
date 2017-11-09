# SDM-PresencePreProc

Files and functions to assist with pre-processing presence data for SDMs

The main functions are contained in sdmPresencePreProc.py. 

Additional helper functions are contained in Helper.py. 

Wrapper scripts, with the prefix 'wrp', are user-friendly scripts to call specific functions. These are intended to be edited as needed to plug in the desired parameter values.

The functions should be run in this order:
-- SplitBiotics
-- AddInitFlds
-- CullDuplicates
-- MergeData
-- SpatialCluster

Direct any questions and bug reports to Kirsten Hazler.
