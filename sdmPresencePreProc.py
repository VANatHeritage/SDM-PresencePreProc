# SDM-presencePreProc.py
# Version:  Python 2.7.5
# Creation Date: 2017-10-31
# Last Edit: 2018-02-22
# Creator:  Kirsten Hazler
#
# Summary: 
# Definitions and functions need to prepare SDM presence data for editing and modeling.
# -------------------------------------------------------------------------------------

# Import Helper module and functions
import Helper
from Helper import *

# Define the fields to add
class Field:
   def __init__(self, Name = '', Type = '', Length = ''):
      self.Name = Name
      self.Type = Type
      self.Length = Length

# Initial fields for editing
fldSpCode = Field('sp_code', 'TEXT', 12) # Code to identify species. Example: 'clemaddi'. If subspecies, use 12 letter code
fldSrcTab = Field('src_table', 'TEXT', 50) # Code to identify source dataset. Example: 'biotics'
fldSrcID = Field('src_id', 'TEXT', 60) # Unique ID identifying source table and observation
fldUse = Field('use', 'SHORT', '') # Binary: Eligible for use in model training (1) or not (0)
fldUseWhy = Field('use_why', 'TEXT', 50) # Comments on eligibility for use
fldDateCalc = Field('dateCalc', 'TEXT', 10) # Date in standardized yyyy-mm-dd format
fldDateFlag = Field('dateFlag', 'SHORT', '') # Flag uncertain year. 0 = certain; 1 = uncertain
fldRA = Field('SFRACalc', 'TEXT', 25) # Source feature representation accuracy
fldNeedEdit = Field('needEdit', 'SHORT', '') # Flag for editing. 0 = okay; 1 = needs edits; 2 = edits done
fldIsDup = Field('isDup', 'SHORT', '') # Flag to identify duplicate records based on src_id field. 0 = no duplicates; 1 = duplicates present; 2 = duplicates have been removed
fldRev = Field('rev', 'SHORT', '') # Flag for review. 0 = okay; 1 = needs review; 2 = review done
fldComments = Field('revComments', 'TEXT', 250) # Field for review/editing comments

initFields = [fldSpCode, fldSrcTab, fldSrcID, fldUse, fldUseWhy, fldDateCalc, fldDateFlag, fldRA, fldNeedEdit, fldIsDup, fldRev, fldComments]

# Additional fields for automation
fldSFID = Field('SF_ID', 'LONG', '') # Source feature ID (Biotics data only)
fldEOID = Field('EO_ID', 'LONG', '') # Element occurrence ID (interpreted for non-Biotics data)
fldRaScore = Field('raScore', 'SHORT', '') # Quality score based on Representation Accuracy
fldDateScore = Field('dateScore', 'SHORT', '') # Quality score based on date
fldPQI = Field('pqiScore', 'SHORT', '') # Composite quality score ("Point Quality Index")
fldGrpUse = Field('grpUse', 'LONG', '') # Identifies highest quality records in group (1) versus all other records (0)

addFields = [fldSFID, fldEOID, fldRaScore, fldDateScore, fldPQI, fldGrpUse]
# list of all fields for dissolving in MergeData
initDissList = ['sp_code','src_table','src_id','use','use_why','dateCalc','dateFlag','SFRACalc','needEdit','isDup','rev','revComments','SF_ID','EO_ID','raScore','dateScore','pqiScore','grpUse']

def SplitBiotics(inFeats, outGDB, inXwalk = "#", fldOutCode = "#", init = True):
   '''Splits a standard input Biotics dataset into multiple datasets based on element codes'''
   
   # Get list of unique values in element code field
   elcodes = unique_values(inFeats, 'ELCODE')
   
   srcTab = arcpy.Describe(inFeats).Name
   
   for code in elcodes:
      # Select the records with the element code
      where_clause = "%s = '%s'" % ('ELCODE', code)
      arcpy.MakeFeatureLayer_management (inFeats, 'lyrFeats', where_clause)
      
      # generate species code from SNAME
      spCode = unique_values('lyrFeats', 'SNAME')[0]
      spCode = spCode.replace('(','').replace(')', '') # remove any parentheses
      spCode = spCode.replace('var. ','').replace('ssp. ','') # remove var. and ssp.
      spCode = (spCode.lower()).split(" ")[0:3] # take first 3 strings
      spCode = ''.join([i[0:4] for i in spCode]) # collapse into code
      
      if inXwalk != '#':
         # Convert crosswalk table to GDB table
         outTab = 'in_memory' + os.sep + 'codeCrosswalk'
         arcpy.ExcelToTable_conversion (inXwalk, outTab)
         # Create a data dictionary from the crosswalk table
         codeDict = TabToDict(outTab, 'ELCODE', fldOutCode)
         
         try:
            # Determine the output name from the data dictionary
            outName = codeDict[code]
            outFeats = outGDB + os.sep + outName
   
            # Export the selected records to a new feature class using the output code as the name
            if init:
               AddInitFlds('lyrFeats', outGDB, 'SF_ID', 'OBSDATE', code)
            else:
               arcpy.CopyFeatures_management('lyrFeats', outFeats)
               printMsg('Created feature class %s for elcode %s' % (outName, code))
            
         except:
            # Export the selected records to a new feature class using elcode as the name
            printMsg('Unable to find output codename for elcode %s' % code)
            printMsg('Saving under derived name instead.')
            outFeats = outGDB + os.sep + spCode
            if init:
               AddInitFlds('lyrFeats', outGDB, spCode, 'SF_ID', 'OBSDATE', spCode)
            else:
               arcpy.CopyFeatures_management('lyrFeats', outFeats)
               printMsg('Created feature class %s for elcode %s' % (outName, code))
      else:
         outFeats = outGDB + os.sep + spCode
         if init:
            AddInitFlds('lyrFeats', outGDB, spCode, 'SF_ID', 'OBSDATE', spCode)
         else:
            arcpy.CopyFeatures_management('lyrFeats', outFeats)
            printMsg('Created feature class %s for elcode %s' % (outName, code))

def AddInitFlds(inPolys, outGDB, spCode, fldDate, fldID = "#", srcTab = '#'):
   '''Adds and populates initial standard data fields need for data review, QC, and editing. '''
   # check if polygon type
   if arcpy.Describe(inPolys).shapeType != 'Polygon':
      raise Exception('Input dataset is not of type Polygon. Convert to polygon and re-run.')
   if srcTab == '#':
      srcTab = arcpy.Describe(inPolys).Name
      srcTab =  srcTab.replace('.shp','')
   outPolys = outGDB + os.sep + srcTab
   
      # Unique ID
   if fldID == "#":
      arcpy.AddField_management(inPolys, 'orfid', 'LONG','')
      fldID = str(arcpy.Describe(inPolys).Fields[0].Name)
      arcpy.CalculateField_management(inPolys, 'orfid', '!' + fldID + '!', 'PYTHON')
      fldID = 'orfid'
   
   # Make a fresh copy of the data
   arcpy.CopyFeatures_management (inPolys, outPolys)
   
   # Add all the initial fields
   for f in initFields:
      try:
         arcpy.AddField_management (outPolys, f.Name, f.Type, '', '', f.Length)
         printMsg('Field %s added.' % f.Name)
      except:
         printMsg('Field %s already exists. Skipping...' % f.Name)
   
   # Populate some fields
   # Source table
   expression = "'%s'" % srcTab
   arcpy.CalculateField_management (outPolys, fldSrcTab.Name, expression, 'PYTHON')
   printMsg('Source table field set to "%s".' % srcTab)
   
   # Species Code
   expression = "'%s'" % spCode
   arcpy.CalculateField_management (outPolys, fldSpCode.Name, expression, 'PYTHON')
   printMsg('Species code field set to "%s".' % spCode)
   
   expression = "'%s-' + '!%s!'" % (srcTab, fldID)
   arcpy.CalculateField_management (outPolys, fldSrcID.Name, expression, 'PYTHON')
   printMsg('Unique ID field populated.')
   
   # Date
   codeblock = """def getStdDate(Date):
      # Import regular expressions module
      import re
      
      # Set up some regular expressions for pattern matching dates
      p1 = re.compile(r'^[1-2][0-9][0-9][0-9]-[0-1][0-9]-[0-9][0-9]$') # yyyy-mm-dd
      p2 = re.compile(r'^[1-2][0-9][0-9][0-9]-[0-1][0-9]$') # yyyy-mm
      p3 = re.compile(r'^[1-2][0-9][0-9][0-9]-?$') # yyyy or yyyy-
      p4 = re.compile(r'^[0-9][0-9]?/[0-9][0-9]?/[1-2][0-9][0-9][0-9]$') # m/d/yyyy or mm/dd/yyyy
      p4m = re.compile(r'^[0-9][0-9]?/') # to extract month
      p4d = re.compile(r'/[0-9][0-9]?/') # to extract day
      
      Date = str(Date)
      if p1.match(Date):
         yyyy = p1.match(Date).group()[:4]
         mm = p1.match(Date).group()[5:7]
         dd = p1.match(Date).group()[8:10]
      elif p2.match(Date):
         yyyy = p2.match(Date).group()[:4]
         mm = p2.match(Date).group()[5:7]
         dd = '00'
      elif p3.match(Date):
         yyyy = p3.match(Date).group()[:4]
         mm = '00'
         dd = '00'
      elif p4.match(Date):
         # This is a pain in the ass.
         yyyy = p4.match(Date).group()[-4:]
         mm = p4m.search(Date).group().replace('/', '').zfill(2)
         dd = p4d.search(Date).group().replace('/', '').zfill(2)
      else: 
         yyyy = '0000'
         mm = '00'
         dd = '00'
      
      yyyymmdd = yyyy + '-' + mm + '-' + dd
      return yyyymmdd"""
   expression = 'getStdDate(!%s!)' % fldDate
   arcpy.CalculateField_management (outPolys, fldDateCalc.Name, expression, 'PYTHON', codeblock)
   printMsg('Standard date field populated.')
   
   # Date certainty (of year)
   codeblock = """def flagDate(Date):
      if Date == '0000-00-00':
         return 1
      else:
         return None"""
   expression = 'flagDate(!%s!)' % fldDateCalc.Name
   arcpy.CalculateField_management (outPolys, fldDateFlag.Name, expression, 'PYTHON', codeblock)
   printMsg('Date flag field populated.')
   
   return outPolys
   
def CullDuplicates(inPolys, fldSrcID = 'src_id', fldDateCalc = 'dateCalc', fldIsDup = 'isDup'):
   '''Removes duplicate records where possible; marks records for review.
      Sets value for 'isDup' field as follows:
      0 = no duplicates
      1 = duplicates present
      2 = duplicates removed'''

   # Get initial record count
   numPolysInit = countFeatures(inPolys)
   printMsg('There are %s polygons to start.' % str(numPolysInit))
   
   # Get list of unique IDs
   idList = unique_values(inPolys, fldSrcID)
   numID = len(idList)
   printMsg('There are %s unique IDs.' % str(numID))
   
   if numPolysInit != numID:
      for id in idList:
         printMsg('Working on ID %s' %id)
         
         # Select the set of records with that ID
         where_clause1 = "%s = '%s'" % (fldSrcID, id)
         arcpy.MakeFeatureLayer_management (inPolys, 'lyrPolys', where_clause1)
         
         # Count the records
         numPolys = countFeatures('lyrPolys')
         
         print 'Your field name is %s' % fldIsDup
         
         if numPolys == 1:
            # set isDup to 0
            arcpy.CalculateField_management ('lyrPolys', fldIsDup, 0, 'PYTHON')
            printMsg('There are no duplicate records for this ID.')
         else:
            # set isDup to 1
            arcpy.CalculateField_management ('lyrPolys', fldIsDup, 1, 'PYTHON')
            printMsg('This ID has duplicate records. Culling...')
            
            # Find the maximum standard date value
            dateList = unique_values('lyrPolys', fldDateCalc)
            maxDate = max(dateList)
         
            # Select any records where the date is less than the maximum AND the date is not 0000-00-00
            where_clause2 = "%s < '%s' AND %s <> '0000-00-00'" % (fldDateCalc, maxDate, fldDateCalc)
            arcpy.MakeFeatureLayer_management ('lyrPolys', 'dupPolys', where_clause2)
            
            # Delete the selected records
            arcpy.DeleteRows_management ('dupPolys')
            
            # Count the remaining records
            arcpy.MakeFeatureLayer_management (inPolys, 'lyrPolys', where_clause1)
            numPolys = countFeatures('lyrPolys')
            if numPolys == 1:
               # set isDup to 2
               arcpy.CalculateField_management ('lyrPolys', fldIsDup, 2, 'PYTHON')
               printMsg('No duplicates remain for this ID.')
            else:
               printMsg('There are still duplicates for this ID that will need to be manually removed.')
   else:
      arcpy.MakeFeatureLayer_management (inPolys, 'lyrPolys')
      arcpy.CalculateField_management ('lyrPolys', fldIsDup, 0, 'PYTHON')

   # Get final record count
   numPolysFinal = countFeatures(inPolys)
   printMsg('There are %s polygons remaining after cull.' % str(numPolysFinal))
   printMsg('%s polygons were culled.' % str(numPolysInit - numPolysFinal))
   
   return inPolys
   
def MergeData(inGDB, outPolys, inList = "#", spatialRef = "#"):
   '''Merges multiple input datasets into one consolidated set with standard fields.
   Assumption: Inputs are all in same coordinate system.'''
   
   arcpy.env.workspace = inGDB
   if inList == "#":
      inList = arcpy.ListFeatureClasses()
   # Get spatial reference from first feature class in list.
   if spatialRef == '#':
      sr = arcpy.Describe(inList[0]).spatialReference
   else: 
      sr = arcpy.Describe(spatialRef).spatialReference
      
   # Make a new polygon feature class for output
   outPolys_temp = (os.path.basename(outPolys)).replace('.shp','') + '_temp'
   outPolys_temp2 = (os.path.basename(outPolys)).replace('.shp','') + '_notDissolved'
   arcpy.CreateFeatureclass_management (inGDB, outPolys_temp, 'POLYGON', '', '', '', sr)
   printMsg('Output feature class initiated.')
   
   # union individual layers
   inList_u = []
   for i in inList:
      inList_u.append(i + "_u")
   for i in range(0,len(inList)):
      u = arcpy.Union_analysis(inList[i], inList_u[i])

   # Add fields to the output
   for f in initFields:
      arcpy.AddField_management (outPolys_temp, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   for f in addFields:
      arcpy.AddField_management (outPolys_temp, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   
   # Append the dataset to the output
   # union individual layers with respect to all layers
   inList_u2 = []
   for i in inList:
      inList_u2.append(i + "_u2")
   
   # set up dissolve list
   initDissList2 = list(initDissList)
   if '.shp' in outPolys:
      initDissList2.extend(['Shape_Area','Shape_Leng'])
   else: 
      initDissList2.extend(['Shape_Area','Shape_Length'])
   nums = range(0,len(inList))
   for i in nums:
      nums2 = range(0,len(inList))
      nums2.remove(i)
      ul = [inList_u[x] for x in [i] + nums2]
      u_all = arcpy.Union_analysis(ul, "union_all")
      fld = 'FID_' + arcpy.Describe(ul[0]).name
      arcpy.Select_analysis(u_all, inList_u2[i], where_clause = fld + " <> -1")
      arcpy.Append_management (inList_u2[i], outPolys_temp, 'NO_TEST')
      # dissolve eliminates polys that are EXACT duplicates, since initDissList includes all fields
      arcpy.Dissolve_management(outPolys_temp, outPolys_temp2, initDissList2, "", "SINGLE_PART")
   
   # get rid of all temp files
   garbagePickup(inList_u + inList_u2 + [outPolys_temp] + ["union_all"])
   printMsg('Data merge complete.')
   
   try:
      MarkSpatialDuplicates(outPolys_temp2, fldDateCalc = 'dateCalc', fldSFRA = 'SFRACalc', fldUse = 'use', fldUseWhy = 'use_why', fldRaScore = 'raScore')
   except:
      arcpy.DeleteField_management('lyrPolys', 'sdc')
      printMsg('Spatial duplicate identification failed; make sure output file is not being accessed in other programs and try re-running MarkSpatialDuplicates on: ' + str(outPolys_temp2))
      return
   # dissolve polygons
   try:
      arcpy.Dissolve_management(outPolys_temp2, outPolys, initDissList, "", "SINGLE_PART")
   except:
      printMsg('Final dissolve failed. Need to dissolve on all attributes (except fid/shape/area) to finalize dataset: ' + str(outPolys_temp2))
      return
   
   garbagePickup([outPolys_temp2])
   return outPolys
   
def MarkSpatialDuplicates(inPolys, fldDateCalc = 'dateCalc', fldSFRA = 'SFRACalc', fldUse = 'use', fldUseWhy = 'use_why', fldRaScore = 'raScore'):
   '''Internal function for MergeData. Sets raScore values, and identifies
   spatial duplicates. It sets fldUse = 1 for the most recent
   polygon among exact duplicates, and all others to 0. If duplicates
   have the same date, fldSFRA is used to rank them (higher preferred).'''
   
   # check RA values
   rau = unique_values(inPolys, fldSFRA)
   notin = list()
   for r in rau:
      if str(r) not in ['Very High', 'High', 'Medium', 'Low', 'Very Low']:
         notin.append(r)
         
   if len(notin) > 0:
      printMsg("Some '" + fldSFRA + "' values not in allowed RA values: ['" + str("','".join(notin)) + "']")
      printMsg("These will receive an " + fldRaScore + " value of 0.")
      #return?
   
   fldSDC = 'sdc'
   # Get initial record count
   arcpy.MakeFeatureLayer_management (inPolys, 'lyrPolys')
   arcpy.AddField_management('lyrPolys', fldSDC)
   arcpy.CalculateField_management('lyrPolys', fldSDC, 0, 'PYTHON')
   
   # initiate fldUseWhy with empty string for db/shapefile compatiblity
   arcpy.CalculateField_management('lyrPolys', fldUseWhy, '""', 'PYTHON')
   
   # Get list of unique IDs
   idCol = arcpy.Describe('lyrPolys').fieldInfo.getFieldName(0)
   idList = unique_values(inPolys, idCol)
   numID = len(idList)
   printMsg('There are %s unique polygons.' % str(numID))
   
   # set raScore
   q = "%s = 'Very High'" % fldSFRA
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", q)
   arcpy.CalculateField_management('lyrPolys', fldRaScore, 5, 'PYTHON')
   q = "%s = 'High'" % fldSFRA
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", q)
   arcpy.CalculateField_management('lyrPolys', fldRaScore, 4, 'PYTHON')
   q = "%s = 'Medium'" % fldSFRA
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", q)
   arcpy.CalculateField_management('lyrPolys', fldRaScore, 3, 'PYTHON')
   q = "%s = 'Low'" % fldSFRA
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", q)
   arcpy.CalculateField_management('lyrPolys', fldRaScore, 2, 'PYTHON')
   q = "%s = 'Very Low'" % fldSFRA
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", q)
   arcpy.CalculateField_management('lyrPolys', fldRaScore, 1, 'PYTHON')
   q = "%s IS NULL" % fldRaScore
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", q)
   arcpy.CalculateField_management('lyrPolys', fldRaScore, 0, 'PYTHON')
   
   print 'Updating %s column...' % fldUse
   
   where_clause = "%s = 0" % fldSDC
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", where_clause)
   numPolys = countFeatures('lyrPolys')
   
   printMsg('Identifying spatial duplicates...')
   while numPolys > 0:
      id = min(unique_values('lyrPolys',idCol))
      # printMsg('Working on ID %s' %id)
      
      # Select the next un-assigned record
      where_clause1 = "%s = %s" % (idCol, id)
      arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", where_clause1)
      arcpy.SelectLayerByLocation_management('lyrPolys', "ARE_IDENTICAL_TO", 'lyrPolys', selection_type =  "ADD_TO_SELECTION")
      arcpy.CalculateField_management('lyrPolys', fldSDC, 1, 'PYTHON') # has been checked; set to 1
      
      # Count the records
      numPolys = countFeatures('lyrPolys')
      
      if numPolys == 1:
         # set isDup to 0
         arcpy.CalculateField_management('lyrPolys', fldUse, 1, 'PYTHON')
      else:
         # set all selected to 0 to start
         arcpy.CalculateField_management('lyrPolys', fldUse, 0, 'PYTHON')
         arcpy.CalculateField_management('lyrPolys', fldUseWhy, '"spatial duplicate"' , 'PYTHON')
         
         # Find the maximum RA value
         raList = unique_values('lyrPolys', 'raScore')
         maxRa = max(raList)
         
         # Unselect any records where the RA is less than the maximum
         where_clause2 = "raScore < %s" % (maxRa)
         arcpy.SelectLayerByAttribute_management('lyrPolys',"REMOVE_FROM_SELECTION", where_clause2)
         
         # Find the maximum standard date value
         dateList = unique_values('lyrPolys', fldDateCalc)
         maxDate = max(dateList)
      
         # Unselect any records where the date is less than the maximum
         where_clause2 = "%s < '%s'" % (fldDateCalc, maxDate)
         arcpy.SelectLayerByAttribute_management('lyrPolys',"REMOVE_FROM_SELECTION", where_clause2)
         
         # Count the remaining records, assign 1 to lowest ID number
         numPolys = countFeatures('lyrPolys')
         if numPolys == 1:
            arcpy.CalculateField_management ('lyrPolys', fldUse, 1, 'PYTHON')
         else:
            idList = unique_values('lyrPolys', idCol)
            minID = min(idList)
            where_clause2 = "%s <> %s" % (idCol, minID)
            arcpy.SelectLayerByAttribute_management('lyrPolys',"REMOVE_FROM_SELECTION", where_clause2)
            arcpy.CalculateField_management ('lyrPolys', fldUse, 1, 'PYTHON')
         arcpy.CalculateField_management ('lyrPolys', fldUseWhy, '""', "PYTHON")
      
      # select remaining unassigned polys
      where_clause = "%s = 0" % fldSDC
      arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", where_clause)
      numPolys = countFeatures('lyrPolys')

   # Get final record count
   numPolysFinal = countFeatures(inPolys)
   arcpy.SelectLayerByAttribute_management('lyrPolys',"CLEAR_SELECTION")
   arcpy.DeleteField_management('lyrPolys', fldSDC)
   
   return inPolys
   
############################################################################
###################### USER INPUT SECTION BEGINS HERE ######################
############################################################################

### Usage Notes:

# - Available functions:
#     - SplitBiotics(inFeats, inXwalk, fldOutCode, outGDB)
#        - inFeats: the input feature class you want to split
#        - inXwalk: the input crosswalk file (must be an Excel file)
#        - fldOutCode: the field in the crosswalk table containing the output code to use for feature class names (should not contain any spaces or weird characters)
#        - outGDB: geodatabase to contain the output feature classes 
#        - init: Flag indicating whether to automatically run AddInitFlds on split feature classes

#     - AddInitFlds(inPolys, spCode, fldID, fldDate, outPolys, srcTab)
#        - inPolys: the input polygon feature class you want to pre-process
#        - outGDB: the output geodatabase (must already exist)
#        - spCode: the 8-character species code
#        - fldDate: the field containing the observation dates
#        - fldID: the field containing the record ID you want to use to identify duplicates (if left "#", the file ID will be used)
#        - srcTab: the data source table code (recommended to leave "#", which uses the file name)

#     - CullDuplicates(inPolys, fldSrcID = 'src_id', fldDateCalc = 'dateCalc', fldIsDup = 'isDup')
#        - inPolys: the input feature class (typically outPolys from the previous function)
#        - fldSrcID: field with standardized ID (leave blank; it will use 'src_id')
#        - fldDateCalc: field with standardized date (leave blank; it will use 'dateCalc')
#        - fldIsDup: field identifying duplicates (leave blank; it will use 'isDup')

#     - MergeData(inList, outPolys)
#        - inList: the list of datasets to merge
#        - outPolys: the output merged polygon feature class
#        - spatialRef: a feature class with the template projection. If not specified, the projection from the first in the list will be used.


### RECOMMENDED WORKFLOW
# First, split the master, multiple-species feature class from Biotics into multiple, single-species feature classes using the "SplitBiotics" function. Then, for each species:
# 1. Run the "AddInitFields" function on the species' Biotics dataset
# 2. Run the "CullDuplicates" function on the output from step 1
# 3. Inspect the output. Fix dates as needed, wherever the dateCalc field is '0000-00-00'. 
      # You can change the dateCalc field to '0000-00-01' if the date cannot be determined and it is a duplicate record that should be culled.
# 4. Run the "CullDuplicates" function on your output file again, if duplicates remained.
# 5. Inspect the output and edit as needed.
      # Set the "use" field to 0 for any records that should not be used, either because it is a remaining duplicate, has an indeterminate date, or for any other reason. Explain reasoning in the "use_why" field if desired. Set the "use" field to 1 for all records still eligible for use in model training.
      # Assign a representation accuracy value in the "SFRACalc" field. Valid inputs are: very high, high, medium, low, or very low.
# 6. Repeat steps 1-5 for any additional, non-Biotics data sets for the species, if applicable.
# 7. Run the "MergeData" function to combine the datasets into one. If you only had Biotics data, run the function on a list containing just the one dataset. The function is still necessary to create additional fields.
# 8. Run the "SpatialCluster" function to assign features to groups based on proximity.
# 9. Review and edit the output as needed.
      


# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)

#==============================================================================
# def main():
#    # SET UP YOUR VARIABLES HERE
#    # The input feature class (typically outPolys from the AddInitFlds function)
#    inPolys = r'C:\Testing\SpeciesFeatures.gdb\clemaddi_proc'
# 
#    # The field containing the standardized ID (you should not have to change this)
#    fldSrcID = 'src_id'
# 
#    # The field containing the standardized date (you should not have to change this)
#    fldDateCalc = 'dateCalc'
# 
#    # The field identifying duplicates (you should not have to change this)
#    fldIsDup = 'isDup' 
#    
#    
#    # SET UP THE DESIRED FUNCTION RUN STATEMENTS HERE 
#    CullDuplicates(inPolys, fldSrcID, fldDateCalc, fldIsDup)
#    
#    # End of user input
#    
# if __name__ == '__main__':
#    main()
#==============================================================================
