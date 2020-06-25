# -*- coding: utf-8 -*-
"""
Created on Thu May 10 11:52:23 2018

@author: David Bucklin
"""
# This is the sdmPresencePreProc arctoolbox.

# TODO (list by priority; remove when added)
#  sep. dists., other info. could be stored in a metadata table


# Helper file with all imports, globals variables, helper fn, classes
from tbx_helper import *
# Template dataset (empty dataset with desired fields, used in MergeData)
template_fc = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'template.gdb' + os.sep + 'sdm_merged_template'

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
         displayName="Species biotics ELCODE",
         name="spCode",
         datatype="GPString",
         parameterType="Required",
         direction="Input")

      outFold = arcpy.Parameter(
         displayName="Output folder for geodatabase",
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
         direction="Output",
         multiValue=True)

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
      if params[0].altered:
         v = params[0].value
         f1 = [f.name for f in arcpy.ListFields(v)]
         f2 = ["#"] + f1
         if 'ELCODE' in f1:
            uval = list(set([a[0] for a in arcpy.da.SearchCursor(v, 'ELCODE')]))
            if len(uval) > 1:
               params[1].value = "[multiple]"
            else:
               params[1].value = uval[0]
         # else:
         # params[1].value = ''
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
      elcode = params[1].valueAsText
      outFold = params[2].valueAsText
      fldDate = params[3].valueAsText
      fldSFRA = params[4].valueAsText
      fldEO = params[5].valueAsText
      fldSF = params[6].valueAsText

      if elcode == '[multiple]':
         # spCode = 'multiSpp_' + datetime.today().strftime('%Y%m%d_%H%m')
         elcodes = list(set([a[0] for a in arcpy.da.SearchCursor(inPolys, 'ELCODE')]))
         selFld = 'ELCODE'
      else:
         if elcode in [a.name for a in arcpy.ListFields(inPolys)]:
            elcodes = list(set([a[0] for a in arcpy.da.SearchCursor(inPolys, elcode)]))
            selFld = elcode
         else:
            elcodes = [elcode]
            selFld = None

      outList = []
      for el in elcodes:

         spCode = 'unk_' + el
         for r in csv.DictReader(open(sp_code_lookup)):
            if r['ELCODE_BCD'] == el:
               spCode = r['sp_code_calc']
               break
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

         # Make a fresh copy of the data
         if selFld:
            arcpy.Select_analysis(inPolys, outPolys, selFld + " = '" + el + "'")
         else:
            arcpy.CopyFeatures_management(inPolys, outPolys)

         # Add all the initial fields
         printMsg('Adding fields...')
         # do not try to add fields that already exist
         existFld = [f.name for f in arcpy.ListFields(outPolys)]
         toAdd = [a for a in initFieldsFull if a[0] not in existFld]
         arcpy.AddFields_management(outPolys, toAdd)

         a = arcpy.Describe(outPolys).Fields
         for a1 in a:
            if a1.Type == 'OID':
               fldID = str(a1.Name)
               break

         # Need to set no-calc fields [#] to an existing field. They won't get calculated though
         if fldEO == "#":
            fldEO = fldID
         if fldSF == "#":
            fldSF = fldID
         if fldSFRA == "#":
            fldSFRA = fldID

         printMsg('Calculating fields...')
         fldlist = [fldID, fldSrcFID.Name, fldSrcTab.Name, fldSpCode.Name, fldUse.Name,
                    fldEO, fldEOID.Name, fldSF, fldSFID.Name, fldSFRA, fldSFRACalc.Name, fldRAFlag.Name,
                    fldDate, fldDateCalc.Name, fldDateFlag.Name]
         # if elcode == '[multiple]':
         #   fldlist.append('ELCODE')
         curs = arcpy.da.UpdateCursor(outPolys, fldlist)
         for row in curs:
            row[1] = row[0]
            row[2] = srcTab
            # if elcode == '[multiple]':
            #    for r in csv.DictReader(open(sp_code_lookup)):
            #       if r['ELCODE_BCD'] == row[15]:
            #          row[3] = r['sp_code_calc']
            #          break
            # else:
            row[3] = spCode
            row[4] = '1'
            if fldEO != fldID and str(fldEO) != str(fldEOID.Name):
               row[6] = row[5]
            if fldSF != fldID and str(fldSF) != str(fldSFID.Name):
               row[8] = row[7]
            if fldSFRA != fldID:
               row[10] = row[9]
               if row[9] not in ['Very High', 'High', 'Medium', 'Low', 'Very Low']:
                  row[11] = 1
            # date
            date2 = getStdDate(row[12])
            row[13] = date2
            if date2 == '0000-00-00':
               row[14] = 1
            curs.updateRow(row)

         # Value checks (RA and date)
         ravals =[a[0] for a in arcpy.da.SearchCursor(outPolys, fldRAFlag.Name) if a[0] == 1]
         if len(ravals) > 0:
            printWrng("Some RA values are not in the allowed value list and were marked with `" +
                      fldRAFlag.Name + "` = 1. Make sure to edit `" + fldSFRACalc.Name + "` column for these rows.")
         datevals = [a[0] for a in arcpy.da.SearchCursor(outPolys, fldDateFlag.Name) if a[0] == 1]
         if len(datevals) > 0:
            printWrng("Some date values were not able to be calculated and were marked with `" +
                      fldDateFlag.Name + "` = 1. Make sure to edit `" + fldDateCalc.Name + "` column for these rows.")

         outList = outList + [outPolys]

      params[7].value = outList
      return outList


class MergeData(object):
   def __init__(self):
      self.label = "2. Merge feature occurrence datasets"
      self.description = "Creates a SDM training dataset (polygons), " + \
                         "from one or more feature occurrence datasets, identifying latest date/highest RA" \
                         "polygon in overlap areas. It is necessary to run this even if there is only " \
                         "one feature occurrence dataset."
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

      # exlcude those with use != 1
      lyr_ls = [arcpy.MakeFeatureLayer_management(a, where_clause=fldUse.Name + " = 1") for a in inList]
      p = arcpy.Merge_management(lyr_ls, scratchGDB + os.sep + 'mergePrep')
      arcpy.Append_management(p, temp, "NO_TEST")
      # Integrate should clean up slight boundary mismatches
      arcpy.Integrate_management(temp, "0.1 Meters")

      # check/set RA values
      rau = unique_values(temp, fldSFRACalc.Name)
      if not all([r in ['Very High', 'High', 'Medium', 'Low', 'Very Low'] for r in rau]):
         printWrng("Some '" + fldSFRACalc.Name + "' values are missing or are not in allowed RA values. These will receive an '" + fldRA.Name + "' value of 0.")
         # return?
      def sfra_fn(sfra):
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
            return 0
      curs = arcpy.da.UpdateCursor(temp, [fldSFRACalc.Name, fldRA.Name])
      for row in curs:
         row[1] = sfra_fn(row[0])
         curs.updateRow(row)

      # This approach uses count overlapping polys (requires ArcPro 2.5+)
      printMsg('Generating all unique polygons...')
      temp1 = temp + '_1'
      GetOverlapping([temp], temp1)
      # temp1 has fields uniqID_poly and COUNT_.

      # Set = 0 those which are spatial duplicates (sorting by date/ra to find 'best' polygon)
      lyr = arcpy.MakeFeatureLayer_management(temp1, where_clause='COUNT_ > 1')
      if arcpy.GetCount_management(lyr)[0] != '0':
         printMsg('Setting spatial duplicates to ' + fldUse.Name + ' = 0')
         df = fc2df(lyr, ['OBJECTID', 'uniqID_poly', fldDateCalc.Name, fldRA.Name])
         # sort decreasing by [date, RA, objectid (in case locations have same date/RA)]
         dfmax = df.sort_values([fldDateCalc.Name, fldRA.Name, 'OBJECTID'], ascending=False).drop_duplicates('uniqID_poly')
         # get a list of OIDs for the highest [Date, RA, OBJECTID]
         oids = list(dfmax.OBJECTID)
         oids = [str(o) for o in oids]
         # set those not in the selected list to use = 0
         arcpy.SelectLayerByAttribute_management(lyr, "NEW_SELECTION", where_clause="OBJECTID NOT IN (" + ",".join(oids) + ")")
         curs = arcpy.da.UpdateCursor(lyr, [fldUse.Name, fldUseWhy.Name])
         for row in curs:
            row[0] = 0
            row[1] = 'Spatial duplicate'
            curs.updateRow(row)
         arcpy.SelectLayerByAttribute_management(lyr, "CLEAR_SELECTION")
         del lyr

      # final dissolve
      printMsg("Dissolving polygons on all attributes...")
      dlist = [a for a in initDissList if a != fldSFRACalc.Name]
      arcpy.Dissolve_management(temp1, outPolys, dlist, multi_part="SINGLE_PART")

      return outPolys


class GrpOcc(object):
   def __init__(self):
      self.label = "3. Finalize and assign groups to occurrences"
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

      copyFld(inPolys2, fldID, fldFeatID.Name)

      if params[1].value:
         sepDist = params[1].valueAsText
         # may implement barriers into regular grouping
         if params[4].value:
            barriers = params[4].valueAsText
         else:
            barriers = None

         if not params[3].value:
            # regular grouping
            printMsg("Using regular grouping with distance of " + str(sepDist))
            # original is joined automatically
            SpatialCluster(inFeats=inPolys2, sepDist=sepDist, fldGrpID=grpFld)
         else:
            # network analyst for aquatic occurrences
            printMsg("Using network grouping with distance of " + str(sepDist))
            network = params[3].valueAsText
            tolerance = params[6].valueAsText
            arcpy.DeleteField_management(inPolys2, grpFld)

            # fixed names in network gdb
            flowlines = os.path.dirname(network) + os.sep + 'NHDFlowline'
            catchments = os.path.dirname(os.path.dirname(network)) + os.sep + 'NHDPlusCatchment'
            # fn from PANHP
            inPolys2 = SpatialClusterNetwork(species_pt=None, species_ln=None, species_py=inPolys2,
                                             flowlines=flowlines, catchments=catchments, network=network, dams=barriers,
                                             sep_dist=sepDist, snap_dist=tolerance, output_lines=outLines)
            # returns inPolys2 with group ID column populated
      else:
         # just update column from src_grpid
         # arcpy.CalculateField_management(inPolys2, fldGrpID.Name, '!' + fldEOID.Name + '!', 'PYTHON')
         copyFld(inPolys2, fldEOID.Name, fldGrpID.Name)

      uv = unique_values(inPolys2, fldGrpID.Name)
      if '' in uv or ' ' in uv:
         printWrng('Some grouping ID values in ' + fldGrpID.Name +
                   ' are empty. Make sure to populate these prior to modeling.')
      arcpy.CopyFeatures_management(inPolys2, outPolys)

      return outPolys


# end
