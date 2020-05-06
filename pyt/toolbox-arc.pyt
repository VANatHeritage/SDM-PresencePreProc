# -*- coding: utf-8 -*-
"""
Created on Thu May 10 11:52:23 2018

@author: David Bucklin
"""
# This is the sdmPresencePreProc arctoolbox.

# TODO (list by priority; remove when added)
#  in line selection SpatialClusterNetwork, could choose highest RA/latest date for line/poly associations
#  sep. dists., other info. could be stored in a metadata table
# TODO Aquatic grouping tool:
#  1. updates sdm_grp_id
#  2. Returns table of [unique COMID], feat occur attributes, [line geom], score, etc.
#    - figure out how to select which feat occur attaches to which line (maybe just latest date of all related, or highest score).
#  3. update sdm_grp_id if necessary (if two groups share a line)
#  4. update sdm_use best as possible
#  overall need = GetLinesSimple integrate into grouping network - maybe just update with SDM_Tools from PA group.
#  TODO: Update/test Network with NHDPlusHR.


# Helper file with all imports, helper fn, classes
import arcpy
from tbx_helper import *


class Toolbox(object):
   def __init__(self):
      self.label = "SDM Training Data Prep"
      self.alias = "sdmPresencePreProc"

      # List of tool classes associated with this toolbox (defined classes below)
      self.tools = [AddInitFlds, MergeData, GrpOcc]


class AddInitFlds(object):
   def __init__(self):
      self.label = "1. Create feature occurrence dataset"
      self.description = "Creates a prepared feature occurrence dataset " + \
                         "from one data source (must be polygons). The tool adds a set of fields " + \
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
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input")

      spCode = arcpy.Parameter(
         displayName="Species code",
         name="spCode",
         datatype="GPString",
         parameterType="Required",
         direction="Output")

      outFold = arcpy.Parameter(
         displayName="Output folder (geodatabase with species code created here if doesn't exist)",
         name="outFold",
         datatype="DEFolder",
         parameterType="Required",
         direction="Input")

      fldDate = arcpy.Parameter(
         displayName="Date field",
         name="fldDate",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      fldSFRA = arcpy.Parameter(
         displayName="RA column",
         name="fldSFRA",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      fldEO = arcpy.Parameter(
         displayName="Group (EO ID) column",
         name="fldEO",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      fldSF = arcpy.Parameter(
         displayName="Feature (SF ID) column",
         name="fldSF",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      outFeat = arcpy.Parameter(
         displayName="Output Features",
         name="out_features",
         datatype="DEFeatureClass",
         parameterType="Derived",
         direction="Output")

      fldDate.parameterDependencies = [inPolys.name]
      fldSFRA.parameterDependencies = [inPolys.name]
      fldEO.parameterDependencies = [inPolys.name]
      fldSF.parameterDependencies = [inPolys.name]

      params = [inPolys, spCode, outFold, fldDate, fldSFRA, fldEO, fldSF, outFeat]
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
         if 'OBSDATE' in f1 and not params[3].altered:
            params[3].value = 'OBSDATE'
         params[3].filter.list = f1
         if 'SFRA' in f1 and not params[4].altered:
            params[4].value = 'SFRA'
         params[4].filter.list = f2
         if 'EO_ID' in f1 and not params[5].altered:
            params[5].value = 'EO_ID'
         params[5].filter.list = f2
         if 'SF_ID' in f1 and not params[6].altered:
            params[6].value = 'SF_ID'
         params[6].filter.list = f2
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      arcpy.env.overwriteOutput = True

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
      srcTab = srcTab.replace('.shp', '')
      srcTab = make_gdb_name(srcTab)
      outPolys = outGDB + os.sep + srcTab + '_' + spCode

      params[7].value = outPolys

      # Make a fresh copy of the data
      arcpy.CopyFeatures_management(inPolys, outPolys)

      # Add all the initial fields
      printMsg('Adding fields...')
      for f in initFields:
         try:
            arcpy.AddField_management(outPolys, f.Name, f.Type, '', '', f.Length)
         except:
            printMsg('Field %s already exists. Skipping...' % f.Name)

      # Populate some fields
      # Source table
      expression = "'%s'" % srcTab
      arcpy.CalculateField_management(outPolys, fldSrcTab.Name, expression, 'PYTHON')
      printMsg('Source table field set to "%s".' % srcTab)

      # Species Code
      expression = "'%s'" % spCode
      arcpy.CalculateField_management(outPolys, fldSpCode.Name, expression, 'PYTHON')
      printMsg('Species code field set to "%s".' % spCode)

      # table fid (object/fid)
      a = arcpy.Describe(outPolys).Fields
      for a1 in a:
         if a1.Type == 'OID':
            fldID = str(a1.Name)
            break
      expression = "!%s!" % (fldID)
      arcpy.CalculateField_management(outPolys, fldSrcFID.Name, expression, 'PYTHON')
      printMsg('Unique ID field populated.')

      # use
      arcpy.CalculateField_management(outPolys, fldUse.Name, '1', "PYTHON")

      # EO_ID and SF_ID
      if fldEO != "#" and str(fldEO) != str(fldEOID.Name):
         expression = "!%s!" % fldEO
         arcpy.CalculateField_management(outPolys, fldEOID.Name, expression, 'PYTHON')
         printMsg('%s field set to "%s".' % (fldEOID.Name, fldEO))
      if fldSF != "#" and str(fldSF) != str(fldSFID.Name):
         expression = "!%s!" % fldSF
         arcpy.CalculateField_management(outPolys, fldSFID.Name, expression, 'PYTHON')
         printMsg('%s field set to "%s".' % (fldSFID.Name, fldSF))
      if fldSFRA != "#":
         expression = "!%s!" % fldSFRA
         arcpy.CalculateField_management(outPolys, fldSFRACalc.Name, expression, 'PYTHON')
         printMsg('%s field set to "%s".' % (fldSFRACalc.Name, fldSFRA))

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
      arcpy.CalculateField_management(outPolys, fldDateCalc.Name, expression, 'PYTHON', codeblock)
      printMsg('Standard date field populated.')

      # Date certainty (of year)
      codeblock = """def flagDate(Date):
         if Date == '0000-00-00':
            return 1
         else:
            return None"""
      expression = 'flagDate(!%s!)' % fldDateCalc.Name
      arcpy.CalculateField_management(outPolys, fldDateFlag.Name, expression, 'PYTHON', codeblock)
      printMsg('Date flag field populated.')

      arcpy.MakeFeatureLayer_management(outPolys, 'outPolys')
      q = "%s NOT IN ('Very High','High','Medium','Low','Very Low')" % fldSFRACalc.Name
      arcpy.SelectLayerByAttribute_management('outPolys', 'NEW_SELECTION', q)
      arcpy.CalculateField_management('outPolys', fldRAFlag.Name, 1, "PYTHON")
      if (int(arcpy.GetCount_management('outPolys')[0]) > 0):
         printMsg(
            "Some RA values are not in the allowed value list and were marked with '%s' = 1. Make sure to edit '%s' column for these rows." % (
            fldRAFlag.Name, fldSFRACalc.Name))
      arcpy.SelectLayerByAttribute_management('outPolys', 'CLEAR_SELECTION')

      return outPolys


class MergeData(object):
   def __init__(self):
      self.label = "2. Merge feature occurrence datasets"
      self.description = "Creates a SDM training dataset (polygons), " + \
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
         displayName="Output feature class (must be in geodatabase)",
         name="outPolys",
         datatype="DEFeatureClass",
         parameterType="Derived",
         direction="Output")

      inList = arcpy.Parameter(
         displayName="List of feature classes - if none selected, all will be used",
         name="inList",
         datatype="GPString",
         parameterType="Optional",
         direction="Input",
         multiValue=True)

      spatialRef = arcpy.Parameter(
         displayName="Spatial reference for ouput",
         name="spatialRef",
         datatype="GPSpatialReference",
         parameterType="Optional",
         direction="Input")

      inList.parameterDependencies = [inGDB.name]

      params = [inGDB, outPolys, inList, spatialRef]
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
         f1 = arcpy.ListFeatureClasses(feature_type='Polygon')
         params[2].filter.list = f1

      # if (params[0].value and not params[1].altered) or (params[0].value and not params[0].hasBeenValidated):
      #   # run only if new value
      #   params[1].value = params[0].valueAsText + os.sep + 'featOccur_merged'

      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      arcpy.env.overwriteOutput = True

      # get date
      today = datetime.today().strftime('%Y%m%d')

      inGDB = params[0].valueAsText
      outPolysNm = str(arcpy.Describe(inGDB).name.replace('.gdb', '')) + '_merged_' + today
      outPolys = str(inGDB) + os.sep + outPolysNm
      params[1].value = outPolys
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
         sr = spatialRef

      arcpy.env.outputCoordinateSystem = sr
      arcpy.CreateFeatureclass_management(scratchGDB, 'merged_temp', template=template_fc, spatial_reference=sr)
      temp = scratchGDB + os.sep + 'merged_temp'

      # exlcude those with use = 0
      lyr_ls = [arcpy.MakeFeatureLayer_management(a, where_clause=fldUse.Name + " = 1") for a in inList]
      p = arcpy.Merge_management(lyr_ls, scratchGDB + os.sep + 'mergePrep')
      arcpy.Append_management(p, temp, "NO_TEST")
      arcpy.Integrate_management(temp, "0.1 Meters")

      # check/set RA values
      rau = unique_values(temp, fldSFRACalc.Name)
      notin = list()
      for r in rau:
         if str(r) not in ['Very High', 'High', 'Medium', 'Low', 'Very Low']:
            notin.append(r)
      if len(notin) > 0:
         printWrng(
            "Some '" + fldSFRACalc.Name + "' values not in allowed RA values. These will receive an '" + fldRA.Name + "' value of 0.")
         # return?
      ra_logic = """def fn(sfra):
         if sfra == 'Very High':
            return 5
         elif sfra == 'High':
            return 4
         elif sfra == 'Medium':
            return 3
         elif sfra == 'Low':
            return 2
         elif sfra == 'Very Low':
            return 1
         else:
            return 0"""
      arcpy.CalculateField_management(temp, fldRA.Name, "fn(!" + fldSFRACalc.Name + "!)", code_block=ra_logic)

      # new approach with count overlapping polys
      printMsg('Generating all unique polygons...')
      temp1 = temp + '_1'
      GetOverlapping([temp], temp1)
      # temp1 has fields uniqID_poly and COUNT_.

      # Set = 0 those which are spatial duplicates (using date/ra to find 'best' polygon)
      lyr = arcpy.MakeFeatureLayer_management(temp1, where_clause='COUNT_ > 1')
      if arcpy.GetCount_management(lyr)[0] != '0':
         printMsg('Setting spatial duplicates to ' + fldUse.Name + ' = 0')
         df = fc2df(lyr, ['OBJECTID', 'uniqID_poly', fldDateCalc.Name, fldRA.Name])
         dfmax = df.sort_values([fldDateCalc.Name, fldRA.Name, 'OBJECTID'], ascending=False).drop_duplicates('uniqID_poly')
         # get a list of OIDs for the highest [Date, RA, OBJECTID]
         oids = list(dfmax.OBJECTID)
         oids = [str(o) for o in oids]
         # set those not in the selected list to use = 0
         arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", where_clause="OBJECTID NOT IN (" + ",".join(oids) + ")")
         arcpy.CalculateField_management(lyr, fldUse.Name, '0')
         arcpy.CalculateField_management(lyr, fldUseWhy.Name, "'Spatial duplicate'")
         arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
         del lyr

      # final dissolve
      printMsg("Dissolving polygons on all attributes...")
      dlist = initDissList
      dlist.remove(fldSFRACalc.Name)
      arcpy.Dissolve_management(temp1, outPolys, dlist, multi_part="SINGLE_PART")

      return outPolys


class GrpOcc(object):
   def __init__(self):
      self.label = "3. Finalize/Group occurrences"
      self.description = "Groups occurrences in a merged feature occurrence dataset, " + \
                         "using a seperation distance, optionally across a defined network. " + \
                         "Only points with a sdm_use value of 1 are used."
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      inPolys = arcpy.Parameter(
         displayName="Input Features (polygons)",
         name="inPolys",
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input")

      sepDist = arcpy.Parameter(
         displayName="Separation distance",
         name="sepDist",
         datatype="GPString",
         parameterType="Optional",
         direction="Input")

      grpFld = arcpy.Parameter(
         displayName="Field for group IDs",
         name="grpFld",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      network = arcpy.Parameter(
         displayName="Network dataset (requires Network Analyst extension)",
         name="network",
         datatype="DENetworkDataset",
         parameterType="Optional",
         direction="Input")

      barriers = arcpy.Parameter(
         displayName="Feature barriers",
         name="barriers",
         datatype="DEFeatureClass",
         parameterType="Optional",
         direction="Input")

      outPolys = arcpy.Parameter(
         displayName="Output Features",
         name="outPolys",
         datatype="DEFeatureClass",
         parameterType="Derived",
         direction="Output")

      tolerance = arcpy.Parameter(
         displayName="Maximum distance tolerance",
         name="tolerance",
         datatype="GPString",
         parameterType="Required",
         direction="Input")
      tolerance.value = "100"

      grpFld.parameterDependencies = [inPolys.name]
      params = [inPolys, sepDist, grpFld, network, barriers, outPolys, tolerance]
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
         f1 = list("#")
         for f in arcpy.ListFields(params[0].value):
            f1.append(f.name)
         params[2].filter.list = f1
         if fldGrpID.Name in f1 and not params[2].altered:
            params[2].value = fldGrpID.Name
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      arcpy.env.overwriteOutput = True

      inPolys = params[0].valueAsText
      grpFld = params[2].valueAsText

      # get source table name
      d = arcpy.Describe(inPolys)
      outPolys = d.path + os.sep + d.name + '_forSDM'
      outLines = outPolys + '_lines'
      params[5].value = outPolys

      # take use = 1 subset
      inPolys2 = scratchGDB + os.sep + 'inPolys'
      arcpy.Select_analysis(inPolys, inPolys2, fldUse.Name + ' = 1')
      # Unique ID (OBJECT/FID)
      a = arcpy.Describe(inPolys2).Fields
      for a1 in a:
         if a1.Type == 'OID':
            fldID = str(a1.Name)
            break

      arcpy.CalculateField_management(inPolys2, fldFeatID.Name, '!' + fldID + '!', 'PYTHON')

      if params[1].value:
         sepDist = params[1].valueAsText
         # may implement barriers into regular grouping
         if params[4].value:
            barriers = params[4].valueAsText
         else:
            barriers = "#"

         if not params[3].value:
            # regular grouping
            printMsg("Using regular grouping with distance of " + str(sepDist))
            # original is joined automatically
            SpatialCluster(inFeats=inPolys2, sepDist=sepDist, fldGrpID=grpFld)
            # joingrp = 'grpID'
            # JoinFields(inPolys, fldID, inPolys2, fldID, [joingrp])

            # arcpy.JoinField_management(inPolys, fldID, inPolys2, fldID, [joingrp])
         else:
            # network analyst
            printMsg("Using network grouping with distance of " + str(sepDist))
            network = params[3].valueAsText
            tolerance = params[6].valueAsText
            # feature to point
            # inPt = arcpy.FeatureToPoint_management(in_features=inPolys2, out_feature_class= scratchGDB + os.sep + 'facil', point_location="INSIDE")
            arcpy.DeleteField_management(inPolys2, grpFld)
            # inPolys2 = SpatialClusterNetwork(inPolys2, sepDist, network, barriers, grpFld) # old call

            # fixed names in network gdb
            flowlines = os.path.dirname(network) + os.sep + 'NHDFlowline_Network'
            catchments = os.path.dirname(os.path.dirname(network)) + os.sep + 'Catchment'
            # fn from PANHP
            inPolys2 = SpatialClusterNetwork(species_pt=None, species_ln=None, species_py=inPolys2,
                                             flowlines=flowlines, catchments=catchments, network=network, dams=barriers,
                                             sep_dist=sepDist, snap_dist=tolerance, output_lines=outLines)
            # returns inPolys2 with group ID column populated
      else:
         # just update column from src_grpid
         arcpy.CalculateField_management(inPolys2, fldGrpID.Name, '!' + fldEOID.Name + '!', 'PYTHON')

      uv = unique_values(inPolys2, fldGrpID.Name)
      if '' in uv or ' ' in uv:
         printWrng(
            'Some grouping ID values in ' + fldGrpID.Name + ' are empty. Make sure to populate these prior to modeling.')
      arcpy.CopyFeatures_management(inPolys2, outPolys)

      return outPolys


# GetLines (for aquatics)

class GetLines(object):
   def __init__(self):
      self.label = "4. Select Lines by polygon occurrences"
      self.description = "Takes a prepared polygon feature occurrence dataset " + \
                         "and a lines feature class, with optional associated " + \
                         "area feature classes, and associates lines with polygons. " + \
                         "At least one line will be associated to each polygon if " + \
                         "lines are within the tolerance distance specified."
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      inPolys = arcpy.Parameter(
         displayName="Input Feature Occurrence Dataset (polygons)",
         name="inPolys",
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input")

      inLines = arcpy.Parameter(
         displayName="Input Features (lines)",
         name="inLines",
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input")

      inAreas = arcpy.Parameter(
         displayName="List of input polygons feature classes associated with input line features (NHDArea and NHDWaterbody)",
         name="inAreas",
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input",
         multiValue=True)

      outLines = arcpy.Parameter(
         displayName="Output feature class",
         name="outLines",
         datatype="DEFeatureClass",
         parameterType="Derived",
         direction="Output")

      inPolysID = arcpy.Parameter(
         displayName="Unique polygon ID field",
         name="inPolysID",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      inLinesID = arcpy.Parameter(
         displayName="Unique lines ID field",
         name="inLinesID",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      tolerance = arcpy.Parameter(
         displayName="Maximum distance tolerance",
         name="tolerance",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      inPolysID.parameterDependencies = [inPolys.name]
      inLinesID.parameterDependencies = [inLines.name]

      params = [inPolys, inLines, inAreas, outLines, inPolysID, inLinesID, tolerance]
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
         for f in arcpy.ListFields(params[0].value):
            f1.append(f.name)
         if 'sdm_featid' in f1 and not params[4].altered:
            params[4].filter.list = f1
            params[4].value = 'sdm_featid'
      if params[1].value:
         f1 = list()
         for f in arcpy.ListFields(params[1].value):
            f1.append(f.name)
         if 'Permanent_Identifier' in f1 and not params[5].altered:
            params[5].filter.list = f1
            params[5].value = 'Permanent_Identifier'
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""
      from pandas import DataFrame
      arcpy.env.workspace = scratchGDB
      arcpy.env.overwriteOutput = True

      inPolys = params[0].valueAsText
      inLines = params[1].valueAsText
      inAreas = (params[2].valueAsText).split(';')
      inPolysID = params[4].valueAsText
      inLinesID = params[5].valueAsText
      tolerance = params[6].valueAsText

      nms = arcpy.Describe(inPolys)
      outLines = nms.path + os.sep + nms.name + '_lines'
      params[3].value = outLines

      lyr_all = scratchGDB + os.sep + 'all'
      d = arcpy.CopyFeatures_management(inPolys, lyr_all)

      # get intersections (lines to polys)
      printMsg('Finding intersecting lines by feature...')
      inter = arcpy.Intersect_analysis([d, inLines])
      df = DataFrame(columns=[inPolysID, inLinesID, 'type'])
      if int(str(arcpy.GetCount_management(inter))) > 0:
         df_inter = fc2df(inter, [inPolysID, inLinesID])
         df_inter["type"] = '1_intersection'
         df = df.append(df_inter)

      # get all areawb intersections and associate a line
      printMsg('Finding nearest line in intersecting area features...')
      dl = arcpy.MakeFeatureLayer_management(lyr_all, 'lyr_all')  # for first intersect
      dl2 = arcpy.MakeFeatureLayer_management(lyr_all, 'lyr_all')  # for tracking those polygons that intersect areas
      alines = arcpy.MakeFeatureLayer_management(inLines, 'arealines')
      area_wb = []
      for a in inAreas:
         a1 = arcpy.MakeFeatureLayer_management(a)
         arcpy.SelectLayerByLocation_management(a1, "INTERSECT", dl)  # get intersecting areas
         if int(str(arcpy.GetCount_management(a1))) > 0:
            arcpy.SelectLayerByLocation_management(alines, "COMPLETELY_WITHIN", a1,
                                                   selection_type="ADD_TO_SELECTION")  # select lines within those areas
            arcpy.SelectLayerByLocation_management(dl2, "INTERSECT", a1,
                                                   selection_type="ADD_TO_SELECTION")  # select polys intersecting those areas
            area_wb.extend(unique_values(a1, inLinesID))

      # get lines based on areawb selection, if any
      if len(area_wb) > 0:
         # str1 = '\',\''.join(area_wb)
         # a1 = arcpy.MakeFeatureLayer_management(inLines, 'arealines') #, '"WBArea_Permanent_Identifier" in (\'' + str1 + '\')')

         # a1 is now lines intersecting the intersecting wbareas
         # take subset that do not intersect an area boundary
         # select all first (only necessary for the boundary touches method. Not using since it requires fixed id in 'a1 = ' step above
         # arcpy.SelectLayerByAttribute_management(a1, "NEW_SELECTION")
         # for a in inAreas:
         # arcpy.SelectLayerByLocation_management(a1, "COMPLETELY_WITHIN", a, "#", "ADD_TO_SELECTION")
         # arcpy.SelectLayerByLocation_management(a1, "BOUNDARY_TOUCHES", a, "#", "REMOVE_FROM_SELECTION")

         # spatial join closest (no limit on distance, since these polys already intersect an area feature)
         near_area_wb = arcpy.SpatialJoin_analysis(dl2, alines, scratchGDB + os.sep + 'sj_wb',
                                                   join_operation="JOIN_ONE_TO_ONE", join_type="KEEP_COMMON",
                                                   match_option="CLOSEST")
         df_near_area_wb = fc2df(near_area_wb, [inPolysID, inLinesID], True)
         df_near_area_wb["type"] = "2_nearest_sameareawb"
         df = df.append(df_near_area_wb)

      # make layer from polys including only non-intersecting
      # intersecting do not need further work
      inter_set = list(set(list(df[inPolysID])))
      inter_set = [str(x) for x in inter_set]
      str1 = ','.join(inter_set)
      dl = arcpy.MakeFeatureLayer_management(lyr_all, 'lyr_all', '"' + inPolysID + '" not in (' + str1 + ')')

      # get those within a distance
      if int(str(arcpy.GetCount_management(dl))) > 0:
         printMsg('Finding lines within search tolerance...')
         near = arcpy.SpatialJoin_analysis(dl, inLines, scratchGDB + os.sep + 'sj', join_operation="JOIN_ONE_TO_MANY",
                                           join_type="KEEP_ALL", match_option="WITHIN_A_DISTANCE",
                                           search_radius=tolerance)
         df_near = fc2df(near, [inPolysID, inLinesID])
         df_near["type"] = "3_nearest"
         # final df merge
         df = df.append(df_near)

      df2 = df.groupby([inPolysID, inLinesID]).size().reset_index(name='Score')

      # df to table
      dftab = scratchGDB + os.sep + 'jointab'
      arcpy.Delete_management(dftab)
      df2tab(df2, dftab)

      # table version of inPolys
      arcpy.CopyRows_management(d, "inPolysTab")
      printMsg('Joining lines with polygon table...')

      # copy inLinesID, geom, joining all inPolys data
      str1 = '\',\''.join(list(df2[inLinesID]))
      outl = arcpy.MakeFeatureLayer_management(inLines, 'lines2', inLinesID + ' in (\'' + str1 + '\')')
      linesel = arcpy.CopyFeatures_management(outl, "outl")

      fieldList = [['outl.' + inLinesID, inLinesID], ['jointab.' + inPolysID, inPolysID], ['outl.Shape', 'Shape']]
      where = "outl." + inLinesID + " = jointab." + inLinesID

      # join poly ids to selected lines
      arcpy.MakeQueryTable_management([linesel, 'jointab'], "lines0", in_field=fieldList, where_clause=where)
      arcpy.CopyFeatures_management("lines0", "lines0_feat")

      # join original poly info
      arcpy.MakeQueryTable_management(['lines0_feat', 'inPolysTab'], "lines1",
                                      where_clause='lines0_feat.' + inPolysID + ' = inPolysTab.' + inPolysID)
      arcpy.CopyFeatures_management("lines1", outLines)
      arcpy.DeleteIdentical_management(outLines, fields="Shape;" + inLinesID + ";" + fldGrpID.Name)

      # re-grouping procedure for groups that share a line
      arcpy.Frequency_analysis(outLines, "freq", frequency_fields=inLinesID)
      sums = unique_values('freq', 'FREQUENCY')
      if len(sums) > 1:
         grps0 = max(unique_values(outLines, fldGrpID.Name))
         layer = arcpy.MakeFeatureLayer_management(outLines)
         # update sdm_grpid for the groups which share a line
         with arcpy.da.SearchCursor("freq", ['FREQUENCY', inLinesID]) as sc:
            for row in sc:
               if row[0] > 1:
                  grps1 = grps0 + 1  # new group number
                  grps0 = grps1  # for next time
                  arcpy.SelectLayerByAttribute_management(layer, "NEW_SELECTION", '"' + inLinesID + '" = ' + "'" + str(
                     row[1]) + "'")  # select lines by id
                  uv = ','.join([str(s) for s in unique_values(layer, fldGrpID.Name)])
                  arcpy.SelectLayerByAttribute_management(layer, "NEW_SELECTION",
                                                          '"' + fldGrpID.Name + '" IN (' + uv + ')')  # select lines by group
                  arcpy.CalculateField_management(layer, fldGrpID.Name, grps1, "PYTHON")
                  printMsg('Groups (' + uv + ') combined into one group (' + str(grps1) + ').')
         arcpy.SelectLayerByAttribute_management(layer, "CLEAR_SELECTION")
         arcpy.DeleteIdentical_management(outLines, fields="Shape;" + inLinesID)
      # end re-grouping

      printMsg('File ' + outLines + ' created.')
      return outLines


class GetLinesSimple(object):
   def __init__(self):
      self.label = "4. Select Lines by polygon occurrences"
      self.description = "Takes a prepared polygon feature occurrence dataset " + \
                         "and a lines feature class, and associates lines with polygons. " + \
                         "All lines within tolerance distance will be returned, and " + \
                         "at least one line will be selected for each occurrence."
      self.canRunInBackground = True

   def getParameterInfo(self):
      """Define parameter definitions"""
      inPolys = arcpy.Parameter(
         displayName="Input Feature Occurrence Dataset (polygons)",
         name="inPolys",
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input")

      inLines = arcpy.Parameter(
         displayName="Input Features (lines)",
         name="inLines",
         datatype="GPFeatureLayer",
         parameterType="Required",
         direction="Input")

      outLines = arcpy.Parameter(
         displayName="Output feature class",
         name="outLines",
         datatype="DEFeatureClass",
         parameterType="Derived",
         direction="Output")

      tolerance = arcpy.Parameter(
         displayName="Maximum distance tolerance",
         name="tolerance",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      inLinesID = arcpy.Parameter(
         displayName="Unique lines ID field",
         name="inLinesID",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      params = [inPolys, inLines, outLines, tolerance, inLinesID]
      return params

   def isLicensed(self):
      """Check whether tool is licensed to execute."""
      return True  # tool can be executed

   def updateParameters(self, params):
      """Modify the values and properties of parameters before internal
      validation is performed.  This method is called whenever a parameter
      has been changed. Example would be updating field list after a feature 
      class was selected for a parameter."""
      if params[1].value or params[1].altered:
         f1 = list()
         for f in arcpy.ListFields(params[1].value):
            f1.append(f.name)
         params[4].filter.list = f1
         if 'Permanent_Identifier' in f1 and not params[4].altered:
            params[4].value = 'Permanent_Identifier'
      return

   def updateMessages(self, params):
      """Modify the messages created by internal validation for each tool
      parameter.  This method is called after internal validation."""
      return

   def execute(self, params, messages):
      """The source code of the tool."""

      inPolys = params[0].valueAsText
      inLines = params[1].valueAsText
      tolerance = params[3].valueAsText
      inLinesID = params[4].valueAsText

      nms = arcpy.Describe(inPolys)
      outLines = nms.path + os.sep + nms.name + '_lines'
      params[2].value = outLines

      arcpy.env.workspace = scratchGDB
      arcpy.env.overwriteOutput = True
      arcpy.env.outputCoordinateSystem = inPolys

      tol_dist = tolerance.split(" ")[0]

      a = arcpy.Describe(inLines).Fields
      for a1 in a:
         if a1.Type == 'OID':
            linesOID = str(a1.Name)
            break

      if not outLines:
         nms = arcpy.Describe(inPolys)
         outLines = nms.path + os.sep + nms.name + '_lines'

      lyr_all = scratchGDB + os.sep + 'allpoly'
      d = arcpy.CopyFeatures_management(inPolys, lyr_all)

      # score lines using point relationships
      lyr_line = arcpy.MakeFeatureLayer_management(inLines, 'lyr_line')
      lyr_poly = arcpy.MakeFeatureLayer_management(lyr_all, 'lyr_poly')

      # dissolve polys
      printMsg('Scoring lines...')
      p1 = arcpy.Dissolve_management(lyr_poly, "p1", dissolve_field="", statistics_fields="", multi_part="SINGLE_PART",
                                     unsplit_lines="DISSOLVE_LINES")
      p1_line = arcpy.PolygonToLine_management(p1, "p1_line", neighbor_option="IGNORE_NEIGHBORS")
      p2 = arcpy.Buffer_analysis(lyr_poly, "p2", buffer_distance_or_field=tolerance)

      # clip lines (after selecting those within tolerance)
      l1_poly = arcpy.MakeFeatureLayer_management(p1, 'p1')
      arcpy.SelectLayerByLocation_management(lyr_line, "WITHIN_A_DISTANCE", p1, tolerance, "NEW_SELECTION")
      l1 = arcpy.Clip_analysis(lyr_line, p2, 'l1')
      arcpy.AddField_management(l1, "slength", "FLOAT")
      arcpy.CalculateField_management(l1, "slength", '!shape.length@meters!', "PYTHON")

      # get statistics on lines
      line_pts = arcpy.FeatureVerticesToPoints_management(l1, 'line_pts', point_location="ALL")
      arcpy.Near_analysis(line_pts, p1_line, search_radius="", location="NO_LOCATION", angle="NO_ANGLE",
                          method="PLANAR")
      line_pts_summ = arcpy.Statistics_analysis(line_pts, out_table='line_pts_summ',
                                                statistics_fields="NEAR_DIST STD;NEAR_DIST MEAN;NEAR_DIST RANGE",
                                                case_field=inLinesID + ";slength")

      # calculate score
      arcpy.AddField_management(line_pts_summ, 'score', 'FLOAT')
      arcpy.CalculateField_management(line_pts_summ, 'score',
                                      expression="(" + tol_dist + " - (!MEAN_NEAR_DIST! * (!STD_NEAR_DIST! / !slength!))) / " + tol_dist,
                                      expression_type="PYTHON", code_block="")
      # arcpy.CalculateField_management(line_pts_summ, 'score',  expression= "(" + tol_dist + " - (!MEAN_NEAR_DIST! * (!RANGE_NEAR_DIST! / !slength!))) / " + tol_dist, expression_type="PYTHON", code_block="")

      # output lines
      outLines = arcpy.CopyFeatures_management(lyr_line, out_feature_class=outLines)
      arcpy.JoinField_management(outLines, inLinesID, line_pts_summ, inLinesID, fields="slength;score")

      # calculate a threshold (minimum of the [maximum scores by original feature within tolerance distance])
      inpoly_sj = arcpy.SpatialJoin_analysis(inPolys, outLines, "inpoly_sj", "JOIN_ONE_TO_MANY", "KEEP_COMMON",
                                             match_option="WITHIN_A_DISTANCE", search_radius=tolerance)
      inpoly_max = arcpy.Statistics_analysis(inpoly_sj, "inpoly_max", statistics_fields="score MAX",
                                             case_field=fldFeatID.Name)
      thresh = min(unique_values(inpoly_max, "MAX_score"))
      printMsg("Using a threshold of score >= " + str(thresh) + "...")

      # new layer to select closest by original polygons
      outlines1 = arcpy.MakeFeatureLayer_management(outLines)
      p1 = arcpy.MakeFeatureLayer_management(p1)
      arcpy.SelectLayerByLocation_management(p1, "WITHIN_A_DISTANCE", lyr_line, tolerance,
                                             invert_spatial_relationship="INVERT")
      arcpy.SelectLayerByLocation_management(lyr_poly, "INTERSECT", p1, selection_type="NEW_SELECTION")
      # nearest line by these polys
      ct = arcpy.GetCount_management(lyr_poly)[0]
      if int(ct) > 0:
         printMsg(
            'Appending nearest lines for ' + ct + ' polygon(s) not within tolerance distance (score will == 1)...')
         arcpy.SelectLayerByAttribute_management(lyr_line, selection_type="CLEAR_SELECTION")
         arcpy.Near_analysis(lyr_poly, lyr_line, search_radius="5000 meters")
         getids = ','.join(str(i) for i in unique_values(lyr_poly, "NEAR_FID"))
         arcpy.SelectLayerByAttribute_management(lyr_line, "NEW_SELECTION", '"' + linesOID + '" in (' + getids + ')')
         outlines2 = arcpy.CopyFeatures_management(lyr_line, out_feature_class="outlines2")
         arcpy.AddField_management(outlines2, 'score', 'FLOAT')
         arcpy.CalculateField_management(outlines2, 'score', 1, expression_type="PYTHON")
         arcpy.Append_management(outlines2, outLines, "NO_TEST")

      # use threshold to assign sdm_use value to flowlines
      arcpy.AddField_management(outLines, fldUse.Name, 'INTEGER')
      arcpy.CalculateField_management(outLines, fldUse.Name, expression="fn(!score!," + str(thresh) + ")",
                                      expression_type="PYTHON",
                                      code_block="def fn(s, t):\n   if s >= t:\n      return 1\n   else:\n      return 0\n")

      return outLines
