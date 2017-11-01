# SDM-presencePreProc.py
# Version:  Python 2.7.5
# Creation Date: 2017-10-31
# Last Edit: 2017-11-01
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
fldSpCode = Field('sp_code', 'TEXT', 8)
fldSrcTab = Field('src_table', 'TEXT', 15)
fldSrcID = Field('src_id', 'TEXT', 25)
fldUse = Field('use', 'SHORT', '')
fldUseWhy = Field('use_why', 'TEXT', 50)
fldRev = Field('rev', 'SHORT', '')
fldDateCalc = Field('dateCalc', 'TEXT', 10)
fldRA = Field('SFRACalc', 'TEXT', 25)
fldNeedEdit = Field('needEdit', 'SHORT', '')
fldIsDup = Field('isDup', 'SHORT', '')

initFields = [fldSpCode, fldSrcTab, fldSrcID, fldUse, fldUseWhy, fldRev, fldDateCalc, fldRA, fldNeedEdit, fldIsDup]

# Additional fields for automation
fldSFID = Field('SF_ID', 'LONG', '')
fldEOID = Field('EO_ID', 'LONG', '')
fldRaScore = Field('raScore', 'SHORT', '')
fldDateScore = Field('dateScore', 'SHORT', '')
fldPQI = Field('pqiScore', 'SHORT', '')
fldGrpID = Field('grpID', 'LONG', '')
fldGrpUse = Field('grpUse', 'LONG', '')

addFields = [fldSFID, fldEOID, fldRaScore, fldDateScore, fldPQI, fldGrpID, fldGrpUse]

def AddInitFlds(inPolys, spCode, srcTab, fldID, fldDate, outPolys):
   '''Add and populate initial standard data fields'''
   # Make a fresh copy of the data
   arcpy.CopyFeatures_management (inPolys, outPolys)
   
   # Add all the initial fields
   for f in initFields:
      arcpy.AddField_management (outPolys, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   
   # Populate some fields
   # Source table
   expression = "'%s'" % srcTab
   arcpy.CalculateField_management (outPolys, fldSrcTab.Name, expression, 'PYTHON')
   printMsg('Source table field set to "%s".' % srcTab)
   
   # Species Code
   expression = "'%s'" % spCode
   arcpy.CalculateField_management (outPolys, fldSpCode.Name, expression, 'PYTHON')
   printMsg('Species code field set to "%s".' % spCode)
   
   # Unique ID
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
   
   return outPolys
   
def CullDuplicates(inPolys, fldSrcID = 'src_id', fldDateCalc = 'dateCalc', fldIsDup = 'isDup'):
   # Get initial record count
   numPolysInit = countFeatures(inPolys)
   printMsg('There are %s polygons to start.' % str(numPolysInit))
   
   # Get list of unique IDs
   idList = unique_values(inPolys, fldSrcID)
   numID = len(idList)
   printMsg('There are %s unique IDs.' % str(numID))
   
   for id in idList:
      printMsg('Working on ID %s' %id)
      
      # Select the set of records with that ID
      where_clause1 = "%s = '%s'" % (fldSrcID, id)
      arcpy.MakeFeatureLayer_management (inPolys, 'lyrPolys', where_clause1)
      
      # Count the records
      numPolys = countFeatures('lyrPolys')
      
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
   
   # Get final record count
   numPolysFinal = countFeatures(inPolys)
   printMsg('There are %s polygons remaining after cull.' % str(numPolysFinal))
   printMsg('%s polygons were culled.' % str(numPolysInit - numPolysFinal))
   
   return inPolys
   
def MergeData(inList, outPolys):
   '''Merge multiple datasets into one consolidated set with standard fields.
   Assumption: Inputs are all in same coordinate system.'''
   # Get spatial reference from first feature class in list.
   sr = arcpy.Describe(inList[0]).spatialReference 
   
   # Make a new polygon feature class for output
   basename = os.path.basename(outPolys)
   dirname = os.path.dirname(outPolys)
   arcpy.CreateFeatureclass_management (dirname, basename, 'POLYGON', '', '', '', sr)
   printMsg('Output feature class initiated.')
   
   # Add fields to the output
   for f in initFields:
      arcpy.AddField_management (outPolys, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   for f in addFields:
      arcpy.AddField_management (outPolys, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   
   # Append the dataset to the output
   arcpy.Append_management (inList, outPolys, 'NO_TEST')
   printMsg('Data merge complete.')
   
   return outPolys
   
   
# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)
def main():
   # Set up your variables here
   inBiotics = r'I:\SWAPSPACE\SDM_WorkingGroup\g1g2s2_SDM.gdb\desmorga_dnh'
   inDGIF = r'I:\SWAPSPACE\SDM_WorkingGroup\g1g2s2_SDM.gdb\desmorga_dgif'
   outBiotics = r'C:\Testing\Testing.gdb\preProcBiotics'
   outDGIF = r'C:\Testing\Testing.gdb\preProcDGIF'
   outMerge = r'C:\Testing\Testing.gdb\preProcMerged'
   
   # Include the desired function run statement(s) below
   #AddInitFlds(inBiotics, 'desmorga', 'biotics', 'SF_ID', 'OBSDATE', outBiotics)
   CullDuplicates(outBiotics)
   #AddInitFlds(inDGIF, 'desmorga', 'dgif', 'ObsID', 'ObsDate', outDGIF)
   #CullDuplicates(outDGIF)
   #MergeData([outBiotics, outDGIF], outMerge)
   
   # End of user input
   
if __name__ == '__main__':
   main()
