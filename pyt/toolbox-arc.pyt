# -*- coding: utf-8 -*-
"""
Created on Thu May 10 11:52:23 2018

@author: David Bucklin
"""
# This is the sdmPresencePreProc arctoolbox.
# Everything from here until class(Toolbox)
# is internal functions and field definitions

import arcpy
import os, sys, traceback, re
from datetime import datetime as datetime

from arcpy.sa import *
arcpy.CheckOutExtension("Spatial")

def countFeatures(features):
   '''Gets count of features'''
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count
   
def garbagePickup(trashList):
   '''Deletes Arc files in list, with error handling. Argument must be a list.'''
   for t in trashList:
      try:
         arcpy.Delete_management(t)
         printMsg('File "' + str(t) + '" deleted.')
      except:
         printMsg('Could not delete file "' + str(t) + '".')
         pass
   return      
      
def GetElapsedTime (t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds/60, delta.seconds%60)
   (h, m) = (m/60, m%60)
   deltaString = '%s days, %s hours, %s minutes, %s seconds' % (str(d), str(h), str(m), str(s))
   return deltaString

def printMsg(msg):
   arcpy.AddMessage(msg)
   print msg
   return
   
def printWrng(msg):
   arcpy.AddWarning(msg)
   print 'Warning: ' + msg
   return
   
def printErr(msg):
   arcpy.AddError(msg)
   print 'Error: ' + msg
   return
   
def ProjectToMatch (fcTarget, csTemplate):
   """Project a target feature class to match the coordinate system of a template dataset"""
   # Get the spatial reference of your target and template feature classes
   srTarget = arcpy.Describe(fcTarget).spatialReference # This yields an object, not a string
   srTemplate = arcpy.Describe(csTemplate).spatialReference 

   # Get the geographic coordinate system of your target and template feature classes
   gcsTarget = srTarget.GCS # This yields an object, not a string
   gcsTemplate = srTemplate.GCS

   # Compare coordinate systems and decide what to do from there. 
   if srTarget.Name == srTemplate.Name:
      printMsg('Coordinate systems match; no need to do anything.')
      return fcTarget
   else:
      printMsg('Coordinate systems do not match; proceeding with re-projection.')
      if fcTarget[-3:] == 'shp':
         fcTarget_prj = fcTarget[:-4] + "_prj.shp"
      else:
         fcTarget_prj = fcTarget + "_prj"
      if gcsTarget.Name == gcsTemplate.Name:
         printMsg('Datums are the same; no geographic transformation needed.')
         arcpy.Project_management (fcTarget, fcTarget_prj, srTemplate)
      else:
         printMsg('Datums do not match; re-projecting with geographic transformation')
         # Get the list of applicable geographic transformations
         # This is a stupid long list
         transList = arcpy.ListTransformations(srTarget,srTemplate) 
         # Extract the first item in the list, assumed the appropriate one to use
         geoTrans = transList[0]
         # Now perform reprojection with geographic transformation
         arcpy.Project_management (fcTarget, fcTarget_prj, srTemplate, geoTrans)
      printMsg("Re-projected data is %s." % fcTarget_prj)
      return fcTarget_prj

def TabToDict(inTab, fldKey, fldValue):
   '''Converts two fields in a table to a dictionary'''
   codeDict = {}
   with arcpy.da.SearchCursor(inTab, [fldKey, fldValue]) as sc:
      for row in sc:
         key = sc[0]
         val = sc[1]
         codeDict[key] = val
   return codeDict      

def JoinFields(ToTab, fldToJoin, FromTab, fldFromJoin, addFields):
   '''An alternative to arcpy's JoinField_management, which is unbearably slow.
   
   ToTab = The table to which fields will be added
   fldToJoin = The key field in ToTab, used to match records in FromTab
   FromTab = The table from which fields will be copied
   fldFromJoin = the key field in FromTab, used to match records in ToTab
   addFields = the list of fields to be added'''
   
   codeblock = '''def getFldVal(srcID, fldDict):
      try:
         fldVal = fldDict[srcID]
      except:
         fldVal = None
      return fldVal'''
   
   for fld in addFields:
      printMsg('Working on "%s" field...' %fld)
      fldObject = arcpy.ListFields(FromTab, fld)[0]
      fldDict = TabToDict(FromTab, fldFromJoin, fld)
      printMsg('Established data dictionary.')
      expression = 'getFldVal(!%s!, %s)' % (fldToJoin, fldDict)
      srcFields = arcpy.ListFields(ToTab, fld)
      if len(srcFields) == 0:
         arcpy.AddField_management (ToTab, fld, fldObject.type, '', '', fldObject.length)
      printMsg('Calculating...')
      arcpy.CalculateField_management (ToTab, fld, expression, 'PYTHON', codeblock)
      printMsg('"%s" field done.' %fld)
   return ToTab
   
def SpatialCluster (inFeats, fldID, searchDist, fldGrpID = 'grpID'):
   '''Clusters features based on specified search distance. Features within twice the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   fldID = The field containing unique feature IDs in inFeats
   searchDist = The search distance to use for clustering. This should be half of the max distance allowed to include features in the same cluster. E.g., if you want features within 500 m of each other to cluster, enter "250 METERS"
   fldGrpID = The desired name for the output grouping field. If not specified, it will be "grpID".'''
   
   # Initialize trash items list
   trashList = []
   
   # Delete the GrpID field from the input features, if it already exists.
   try:
      arcpy.DeleteField_management (inFeats, fldGrpID)
   except:
      pass
      
   # Buffer input features
   printMsg('Buffering input features')
   outBuff = scratchGDB + os.sep + 'outBuff'
   arcpy.Buffer_analysis (inFeats, outBuff, searchDist, '', '', 'ALL')
   trashList.append(outBuff)
   
   # Explode multipart  buffers
   printMsg('Exploding buffers')
   explBuff = scratchGDB + os.sep + 'explBuff'
   arcpy.MultipartToSinglepart_management (outBuff, explBuff)
   trashList.append(explBuff)
   
   # Add and populate grpID field in buffers
   printMsg('Adding and populating grouping field in buffers')
   arcpy.AddField_management (explBuff, fldGrpID, 'LONG')
   arcpy.CalculateField_management (explBuff, fldGrpID, '!OBJECTID!', 'PYTHON')
   
   # Spatial join buffers with input features
   printMsg('Performing spatial join between buffers and input features')
   joinFeats = scratchGDB + os.sep + 'joinFeats'
   arcpy.SpatialJoin_analysis (inFeats, explBuff, joinFeats, 'JOIN_ONE_TO_ONE', 'KEEP_ALL', '', 'WITHIN')
   trashList.append(joinFeats)
   
   # Join grpID field to input features
   # This employs a custom function because arcpy is stupid slow at this
   JoinFields(inFeats, fldID, joinFeats, 'TARGET_FID', [fldGrpID])
   
   # Cleanup: delete buffers, spatial join features
   garbagePickup(trashList)
   
   printMsg('Processing complete.')
   
   return inFeats
   
def tbackInLoop():
   '''Standard error handling routing to add to bottom of scripts'''
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = arcpy.GetMessages(1)
   msgList = [pymsg, msgs]

   #printWrng(msgs)
   printWrng(pymsg)
   printMsg(msgs)
   
   return msgList
   
def unique_values(table, field):
   ''' Gets list of unique values in a field.
   Thanks, ArcPy Cafe! https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/'''
   with arcpy.da.SearchCursor(table, [field]) as cursor:
      return sorted({row[0] for row in cursor})

def make_gdb(path):
   ''' Creates a geodatabase if it doesn't exist'''
   path = path.replace("\\", "/")
   if '.gdb' not in path:
      printMsg("Bad geodatabase path name.")
      return False
   folder = path[0:path.rindex("/")]
   name = path[(path.rindex("/")+1):len(path)]
   if not os.path.exists(path):
      try:
         arcpy.CreateFileGDB_management(folder, name)
      except:
         return False
      else:
         printMsg("Geodatabase '" + path + "' created.")
         return True
   else:
      return True

def make_gdb_name(string):
   '''Makes strings GDB-compliant'''
   nm = re.sub('[^A-Za-z0-9]+', '_', string)
   return nm

# used in MergeData
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
      printWrng("Some '" + fldSFRA + "' values not in allowed RA values. These will receive an '" + fldRaScore + "' value of 0.")
      # return?
   
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

### Define the fields to add
class Field:
   def __init__(self, Name = '', Type = '', Length = ''):
      self.Name = Name
      self.Type = Type
      self.Length = Length

# Initial fields for editing
fldSpCode = Field('sp_code', 'TEXT', 12) # Code to identify species. Example: 'clemaddi'. If subspecies, use 12 letter code
fldSrcTab = Field('src_table', 'TEXT', 50) # Code to identify source dataset. Example: 'biotics'
fldSrcID = Field('src_id', 'TEXT', 60) # Unique ID identifying source table and observation
fldSFID = Field('SF_ID', 'LONG', '') # Source feature ID (Biotics data only)
fldEOID = Field('EO_ID', 'LONG', '') # Element occurrence ID (interpreted for non-Biotics data)
fldUse = Field('use', 'SHORT', '') # Binary: Eligible for use in model training (1) or not (0)
fldUseWhy = Field('use_why', 'TEXT', 50) # Comments on eligibility for use
fldDateCalc = Field('dateCalc', 'TEXT', 10) # Date in standardized yyyy-mm-dd format
fldDateFlag = Field('dateFlag', 'SHORT', '') # Flag uncertain year. 0 = certain; 1 = uncertain
fldRA = Field('SFRACalc', 'TEXT', 25) # Source feature representation accuracy
fldNeedEdit = Field('needEdit', 'SHORT', '') # Flag for editing. 0 = okay; 1 = needs edits; 2 = edits done
fldIsDup = Field('isDup', 'SHORT', '') # Flag to identify duplicate records based on src_id field. 0 = no duplicates; 1 = duplicates present; 2 = duplicates have been removed
fldRev = Field('rev', 'SHORT', '') # Flag for review. 0 = okay; 1 = needs review; 2 = review done
fldComments = Field('revComments', 'TEXT', 250) # Field for review/editing comments

initFields = [fldSpCode, fldSrcTab, fldSrcID, fldUse, fldUseWhy, fldDateCalc, fldDateFlag, fldRA, fldNeedEdit, fldIsDup, fldRev, fldComments, fldSFID, fldEOID]

# Additional fields for automation
fldRaScore = Field('raScore', 'SHORT', '') # Quality score based on Representation Accuracy
fldDateScore = Field('dateScore', 'SHORT', '') # Quality score based on date
fldPQI = Field('pqiScore', 'SHORT', '') # Composite quality score ("Point Quality Index")
fldGrpUse = Field('grpUse', 'LONG', '') # Identifies highest quality records in group (1) versus all other records (0)

addFields = [fldRaScore, fldDateScore, fldPQI, fldGrpUse]
# list of all fields for dissolving in MergeData
initDissList = ['sp_code','src_table','src_id','use','use_why','dateCalc','dateFlag','SFRACalc','needEdit','isDup','rev','revComments','SF_ID','EO_ID','raScore','dateScore','pqiScore','grpUse']
### header field data

class Toolbox(object):
   def __init__(self):
      self.label = "SDM Training Data Prep"
      self.alias = "sdmPresencePreProc"
      
      # List of tool classes associated with this toolbox (defined classes below)
      self.tools = [AddInitFlds, MergeData]
      
class AddInitFlds(object):
   def __init__(self):
      self.label = "Create feature occurrence dataset"
      self.description ="Creates a prepared feature occurrence dataset (polygons), " + \
                        "from one data source (must be polygon input), and adds a set of fields " + \
                        "which will be used later when data is merged. It " + \
                        "only outputs to a geodatabase, which will be created " + \
                        "if it doesn't exist already. All feature occurrence datasets " + \
                        "for a given species/element should be output to the same geodatabase."
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      inPolys = arcpy.Parameter(
            displayName="Input Features (polygons)",
            name="inPolys",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
            
      spCode = arcpy.Parameter(
            displayName = "Species code",
            name = "spCode",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Output")
      
      outFold = arcpy.Parameter(
            displayName="Output folder (geodatabase with species code created here if doesn't exist)",
            name="outFold",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
            
      fldDate = arcpy.Parameter(
            displayName = "Date field",
            name = "fldDate",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      
      fldSFRA = arcpy.Parameter(
            displayName = "RA column",
            name = "fldSFRA",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      
      fldEO = arcpy.Parameter(
            displayName = "EO ID column",
            name = "fldEO",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      
      fldSF = arcpy.Parameter(
            displayName = "SF ID column",
            name = "fldSF",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
       
      outFeat = arcpy.Parameter(
            displayName="Output Features",
            name="out_features",
            datatype="GPFeatureLayer",
            parameterType="Derived",
            direction="Output")
            
      fldDate.parameterDependencies = [inPolys.name]
      fldSFRA.parameterDependencies = [inPolys.name]
      fldEO.parameterDependencies = [inPolys.name]
      fldSF.parameterDependencies = [inPolys.name]
      
      params = [inPolys,spCode,outFold,fldDate,fldSFRA,fldEO,fldSF,outFeat]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      if params[0].value:
         f1 = list()
         f2 = list("#")
         for f in arcpy.ListFields(params[0].value):
            f1.append(f.name)
            f2.append(f.name)
         params[3].filter.list = f1
         params[4].filter.list = f2
         params[5].filter.list = f2
         params[6].filter.list = f2
      return
      
   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""
      
      inPolys = params[0].valueAsText
      spCode = params[1].valueAsText
      outFold = params[2].valueAsText
      fldDate = params[3].valueAsText
      fldSFRA = params[4].valueAsText
      fldEO = params[5].valueAsText
      fldSF = params[6].valueAsText
      
      outGDB = outFold + os.sep + spCode + '.gdb'
      
      # check if polygon type
      if not make_gdb(outGDB):
         printErr('Invalid input geodatabase path. Make sure it has a ".gdb" extension.')
         return
      if arcpy.Describe(inPolys).shapeType != 'Polygon':
         raise Exception('Input dataset is not of type Polygon. Convert to polygon and re-run.')

      # get source table name
      srcTab = arcpy.Describe(inPolys).Name
      srcTab =  srcTab.replace('.shp','')
      srcTab = make_gdb_name(srcTab)
      outPolys = outGDB + os.sep + srcTab
      
      params[7].value = outPolys
      
      # Unique ID
      arcpy.AddField_management(inPolys, 'orfid', 'LONG','')
      fldID = str(arcpy.Describe(inPolys).Fields[0].Name)
      arcpy.CalculateField_management(inPolys, 'orfid', '!' + fldID + '!', 'PYTHON')
      fldID = 'orfid'
      
      # Make a fresh copy of the data
      arcpy.CopyFeatures_management (inPolys, outPolys)
      
      # Add all the initial fields
      printMsg('Adding fields...')
      for f in initFields:
         try:
            arcpy.AddField_management (outPolys, f.Name, f.Type, '', '', f.Length)
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
      
      # EO_ID and SF_ID
      if fldEO != "#" and str(fldEO) != str(fldEOID.Name):
         expression = "!%s!" % fldEO
         arcpy.CalculateField_management (outPolys, fldEOID.Name, expression, 'PYTHON')
         printMsg('%s field set to "%s".' % (fldEOID.Name, fldEO))
      if fldSF != "#" and str(fldSF) != str(fldSFID.Name):
         expression = "!%s!" % fldSF
         arcpy.CalculateField_management (outPolys, fldSFID.Name, expression, 'PYTHON')
         printMsg('%s field set to "%s".' % (fldSFID.Name, fldSF))
      
      if fldSFRA != "#":
         expression = "!%s!" % fldSFRA
         arcpy.CalculateField_management (outPolys, fldRA.Name, expression, 'PYTHON')
         printMsg('%s field set to "%s".' % (fldRA.Name, fldSFRA))
      
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
      
      arcpy.MakeFeatureLayer_management (outPolys, 'outPolys')
      q = "%s NOT IN ('Very High','High','Medium','Low','Very Low')" % fldRA.Name
      arcpy.SelectLayerByAttribute_management('outPolys','NEW_SELECTION', q)
      arcpy.CalculateField_management ('outPolys', fldNeedEdit.Name, 1, "PYTHON")
      if (int(arcpy.GetCount_management('outPolys')[0]) > 0):
         printMsg("Some RA values are not in the allowed value list and were marked with '%s' = 1. Make sure to edit '%s' column for these rows." % (fldNeedEdit.Name, fldRA.Name))
      arcpy.SelectLayerByAttribute_management('outPolys', 'CLEAR_SELECTION')
      
      return outPolys
   
# end AddInitFlds


# begin MergeData
class MergeData(object):
   def __init__(self):
      self.label = "Merge feature occurrence datasets"
      self.description ="Creates a SDM training dataset (polygons), " + \
                        "from one or more feature occurrence datasets." + \
                        " It is necessary to run this even if there is only one feature occurrence dataset."
      self.canRunInBackground = True
      
   def getParameterInfo(self):
      """Define parameter definitions"""
      
      inGDB = arcpy.Parameter(
            displayName="Input geodatabase",
            name="inGDB",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
      
      outPolys = arcpy.Parameter(
            displayName = "Output feature class (must be in geodatabase)",
            name = "outPolys",
            datatype = "DEFeatureClass",
            parameterType = "Required",
            direction = "Output")
      
      inList = arcpy.Parameter(
            displayName = "List of feature classes - if none selected, all will be used",
            name = "inList",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input",
            multiValue = True)
      
      spatialRef = arcpy.Parameter(
            displayName = "Spatial reference for ouput",
            name = "spatialRef",
            datatype = "GPSpatialReference",
            parameterType = "Optional",
            direction = "Input")
            
      inList.parameterDependencies = [inGDB.name]
      
      params = [inGDB,outPolys,inList,spatialRef]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      
      if params[0].value:
         arcpy.env.workspace = params[0].valueAsText
         f1 = arcpy.ListFeatureClasses(feature_type = 'Polygon')
         params[2].filter.list = f1
      
      if (params[0].value and not params[1].altered) or (params[0].value and not params[0].hasBeenValidated):
         # run only if new value
         params[1].value = params[0].valueAsText + os.sep + 'featOccur_merged'

      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""
      
      inGDB = params[0].valueAsText
      outPolys = params[1].valueAsText
      if params[2].value:
         inList = (params[2].valueAsText).split(';')
      else:
         inList = "#"
      if params[3].value:
         spatialRef = params[3].valueAsText
      else:
         spatialRef = "#"
      
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
      printMsg('Adding fields...')
      for f in initFields:
         arcpy.AddField_management (outPolys_temp, f.Name, f.Type, '', '', f.Length)
      for f in addFields:
         arcpy.AddField_management (outPolys_temp, f.Name, f.Type, '', '', f.Length)
      
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
      
      # identify spatial duplicates (internal function)
      MarkSpatialDuplicates(outPolys_temp2, fldDateCalc = 'dateCalc', fldSFRA = 'SFRACalc', fldUse = 'use', fldUseWhy = 'use_why', fldRaScore = 'raScore')
      
      # final dissolve
      try:
         arcpy.Dissolve_management(outPolys_temp2, outPolys, initDissList, "", "SINGLE_PART")
      except:
         printMsg('Final dissolve failed. Need to dissolve on all attributes (except fid/shape/area) to finalize dataset: ' + str(outPolys_temp2))
         return
      
      garbagePickup([outPolys_temp2])
      return outPolys