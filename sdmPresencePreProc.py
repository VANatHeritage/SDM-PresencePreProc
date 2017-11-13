# SDM-presencePreProc.py
# Version:  Python 2.7.5
# Creation Date: 2017-10-31
# Last Edit: 2017-11-06
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
fldSpCode = Field('sp_code', 'TEXT', 8) # Code to identify species. Example: 'clemaddi'
fldSrcTab = Field('src_table', 'TEXT', 15) # Code to identify source dataset. Example: 'biotics'
fldSrcID = Field('src_id', 'TEXT', 25) # Unique ID identifying source table and observation
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
fldEOID = Field('EO_ID', 'LONG', '') # Element occurrence ID (Biotics data only)
fldRaScore = Field('raScore', 'SHORT', '') # Quality score based on Representation Accuracy
fldDateScore = Field('dateScore', 'SHORT', '') # Quality score based on date
fldPQI = Field('pqiScore', 'SHORT', '') # Composite quality score ("Point Quality Index")
fldGrpUse = Field('grpUse', 'LONG', '') # Identifies highest quality records in group (1) versus all other records (0)

addFields = [fldSFID, fldEOID, fldRaScore, fldDateScore, fldPQI, fldGrpUse]

def SplitBiotics(inFeats, inXwalk, fldOutCode, outGDB):
   '''Splits a standard input Biotics dataset into multiple datasets based on element codes'''
   # Convert crosswalk table to GDB table
   outTab = 'in_memory' + os.sep + 'codeCrosswalk'
   arcpy.ExcelToTable_conversion (inXwalk, outTab)
   
   # Create a data dictionary from the crosswalk table
   codeDict = TabToDict(outTab, 'ELCODE', fldOutCode)
   
   # Get list of unique values in element code field
   elcodes = unique_values(inFeats, 'ELCODE')
   
   for code in elcodes:
      # Select the records with the element code
      where_clause = "%s = '%s'" % ('ELCODE', code)
      arcpy.MakeFeatureLayer_management (inFeats, 'lyrFeats', where_clause)
      
      try:
         # Determine the output name from the data dictionary
         outName = codeDict[code]
         outFeats = outGDB + os.sep + outName

         # Export the selected records to a new feature class using the output code as the name
         arcpy.CopyFeatures_management('lyrFeats', outFeats)
         printMsg('Created feature class %s for elcode %s' % (outName, code))
         
      except:
         # Export the selected records to a new feature class using elcode as the name
         printMsg('Unable to find output codename for elcode %s' % code)
         printMsg('Saving under elcode name instead.')
         outFeats = outGDB + os.sep + code
         arcpy.CopyFeatures_management('lyrFeats', outFeats)
         

def AddInitFlds(inPolys, spCode, srcTab, fldID, fldDate, outPolys):
   '''Adds and populates initial standard data fields need for data review, QC, and editing. '''
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
   '''Merges multiple input datasets into one consolidated set with standard fields.
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

#     - AddInitFlds(inPolys, spCode, srcTab, fldID, fldDate, outPolys)
#        - inPolys: the input polygon feature class you want to pre-process
#        - spCode: the 8-character species code
#        - srcTab: the data source table code
#        - fldID: the field containing the record ID you want to use to identify duplicates
#        - fldDate: the field containing the observation dates
#        - outPolys: the output feature class

#     - CullDuplicates(inPolys, fldSrcID = 'src_id', fldDateCalc = 'dateCalc', fldIsDup = 'isDup')
#        - inPolys: the input feature class (typically outPolys from the previous function)
#        - fldSrcID: field with standardized ID (leave blank; it will use 'src_id')
#        - fldDateCalc: field with standardized date (leave blank; it will use 'dateCalc')
#        - fldIsDup: field identifying duplicates (leave blank; it will use 'isDup')

#     - MergeData(inList, outPolys)
#        - inList: the list of datasets to merge
#        - outPolys: the output merged polygon feature class


### RECOMMENDED WORKFLOW
# First, split the master, multiple-species feature class from Biotics into multiple, single-species feature classes using the "SplitBiotics" function. Then, for each species:
# 1. Run the "AddInitFields" function on the species' Biotics dataset
# 2. Run the "CullDuplicates" function on the output from step 1
# 3. Inspect the output. Fix dates as needed, wherever the dateCalc field is '0000-00-00'. 
      # You can change the dateCalc field to '0000-00-01' if the date cannot be determined and it is a duplicate record that should be culled.
# 4. Run the #CullDuplicates" function on your output file again, if duplicates remained.
# 5. Inspect the output and edit as needed.
      # Set the "use" field to 0 for any records that should not be used, either because it is a remaining duplicate, has an indeterminate date, or for any other reason. Explain reasoning in the "use_why" field if desired. Set the "use" field to 1 for all records still eligible for use in model training.
      # Assign a representation accuracy value in the "SFRACalc" field. Valid inputs are: very high, high, medium, low, or very low.
# 6. Repeat steps 1-5 for any additional, non-Biotics data sets for the species, if applicable.
# 7. Run the "MergeData" function to combine the datasets into one. If you only had Biotics data, run the function on a list containing just the one dataset. The function is still necessary to create additional fields.
# 8. Run the "SpatialCluster" function to assign features to groups based on proximity.
# 9. Review and edit the output as needed.
      


# Use the section below to enable a function (or sequence of functions) to be run directly from this free-standing script (i.e., not as an ArcGIS toolbox tool)

def main():
   # SET UP YOUR VARIABLES HERE
   inFeats = r'C:\Testing\Testing.gdb\dnhMerge'
   inXwalk = r'I:\SWAPSPACE\K_Hazler\From_Anne\g1g2s1SpeciesList.xlsx'
   fldOutCode = 'CODENAME'
   outGDB = 'C:\Testing\SpeciesFeatures.gdb'
   
   
   # SET UP THE DESIRED FUNCTION RUN STATEMENTS HERE 
   SplitBiotics(inFeats, inXwalk, fldOutCode, outGDB)
   
   # End of user input
   
if __name__ == '__main__':
   main()
