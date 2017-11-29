# SDM-PresencePreProc

Files and functions to assist with pre-processing presence data for SDMs

Most of the main functions are contained in sdmPresencePreProc.py. 

Additional helper functions (including SpatialCluster) are contained in Helper.py. 

Wrapper scripts, with the prefix 'wrp', are user-friendly scripts to call specific functions. These are intended to be edited as needed to plug in the desired parameter values.

The functions should be run in this order:
- SplitBiotics: Splits a Biotics feature class into individual feature classes for each species
- AddInitFlds: Adds and populates a set of fields needed for review/QC/editing
- CullDuplicates: Removes or flags duplicate records
- MergeData: Merges features classes and retains only standard fields
- SpatialCluster: Groups features spatially into clusters based on a specified search distance

Still to do: 
- Function to populate the raScore, dateScore, pqiScore, and grpUse fields (still need to work out details of how we want to implement)

Direct any questions and bug reports to Kirsten Hazler.
Last update: 2017-11-29
