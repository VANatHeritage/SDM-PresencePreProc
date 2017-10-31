# SDM-presencePreProc.py
# Version:  Python 2.7.5
# Creation Date: 2017-10-31
# Last Edit: 2017-10-31
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
fldSrcOID = Field('src_oid', 'LONG', '')
fldUse = Field('use', 'SHORT', '')
fldUseWhy = Field('use_why', 'TEXT', 50)
fldRev = Field('rev', 'SHORT', '')
fldDateCalc = Field('dateCalc', 'TEXT', 10)
fldRA = Field('SFRACalc', 'TEXT', 25)
fldNeedEdit = Field('needEdit', 'SHORT', '')

initFields = [fldSpCode, fldSrcTab, fldSrcOID, fldUse, fldUseWhy, fldRev, fldDateCalc, fldRA, fldNeedEdit]

# Additional fields for automation
fldSFID = Field('SF_ID', 'LONG', '')
fldEOID = Field('EO_ID', 'LONG', '')
fldRaScore = Field('raScore', 'SHORT', '')
fldDateScore = Field('dateScore', 'SHORT', '')
fldPQI = Field('pqiScore', 'SHORT', '')
fldGrpID = Field('grpID', 'LONG', '')
fldGrpUse = Field('grpUse', 'LONG', '')

addFields = [fldSFID, fldEOID, fldRaScore, fldDateScore, fldPQI, fldGrpID, fldGrpUse]

def AddInitFlds(inPolys, spCode, srcTab, outPolys):
   '''Add and populate initial standard data fields'''
   # Make a fresh copy of the data
   arcpy.CopyFeatures_management (inPolys, outPolys)
   
   # Add all the initial fields
   for f in initFields:
      arcpy.AddField_management (outPolys, f.Name, f.Type, '', '', f.Length)
      printMsg('Field %s added.' % f.Name)
   
   # Populate some fields
   expression = "'%s'" % srcTab
   arcpy.CalculateField_management (outPolys, fldSrcTab.Name, expression, 'PYTHON')
   printMsg('Source table field set to "%s"' % srcTab)
   
   expression = "'%s'" % spCode
   arcpy.CalculateField_management (outPolys, fldSpCode.Name, expression, 'PYTHON')
   printMsg('Species code field set to "%s"' % spCode)
   
   try:
      arcpy.CalculateField_management (outPolys, fldSrcOID.Name, '!OBJECTID!', 'PYTHON')
   except:
      arcpy.CalculateField_management (outPolys, fldSrcOID.Name, '!FID!', 'PYTHON')
   printMsg('Source ID field populated.')
   
   return outPolys
   
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
   AddInitFlds(inBiotics, 'desmorga', 'biotics', outBiotics)
   AddInitFlds(inDGIF, 'desmorga', 'dgif', outDGIF)
   MergeData([outBiotics, outDGIF], outMerge)
   
   # End of user input
   
if __name__ == '__main__':
   main()
