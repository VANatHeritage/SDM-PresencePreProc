# Helper functions for python toolbox

import arcpy
import datetime
import os
import re
import sys
import traceback
import pathlib
from datetime import datetime as datetime

arcpy.CheckOutExtension("Spatial")
scratchGDB = r'C:\David\scratch\sdmPresencePreProc.gdb'
# scratchGDB = arcpy.env.scratchGDB
# scratchGDB = "in_memory"


### Define the fields to add
template_fc = os.path.dirname(os.path.abspath(__file__)) + os.sep + 'template.gdb\\sdm_merged_template'
class Field:
   def __init__(self, Name='', Type='', Length=''):
      self.Name = Name
      self.Type = Type
      self.Length = Length


# Initial fields for editing
fldSpCode = Field('sp_code', 'TEXT', 12)  # Code to identify species. Example: 'clemaddi'. If subspecies, use 12 letters
fldSrcTab = Field('src_table', 'TEXT', 50)  # Code to identify source dataset. Example: 'biotics'
fldSrcFID = Field('src_fid', 'LONG', '')  # original source table FID (auto-populated)
fldSFID = Field('src_featid', 'LONG', '')  # original feature's SFID or similar (Source feature ID in Biotics)
fldEOID = Field('src_grpid', 'TEXT', 50)  # original group ID (EO ID in biotics)
fldUse = Field('sdm_use', 'SHORT', '')  # Binary: Eligible for use in model training (1) or not (0)
fldUseWhy = Field('sdm_use_why', 'TEXT', 50)  # Comments on eligibility for use
fldDateCalc = Field('sdm_date', 'TEXT', 10)  # Date in standardized yyyy-mm-dd format
fldDateFlag = Field('sdm_date_flag', 'SHORT', '')  # Flag uncertain year. 0 = certain; 1 = uncertain
fldRA = Field('sdm_ra', 'SHORT', '')  # Source feature representation accuracy
fldSFRACalc = Field('tempSFRACalc', 'TEXT', 20)  # for storing original RA column values for editing
fldRAFlag = Field('sdm_ra_flag', 'SHORT', '')  # Flag for editing. 0 = okay; 1 = needs edits; 2 = edits done
fldFeatID = Field('sdm_featid', 'LONG', '')  # new unique id by polygon
fldGrpID = Field('sdm_grpid', 'TEXT', 50)  # new unique id by group
# fldComments = Field('revComments', 'TEXT', 250) # Field for review/editing comments; dropping in favor of UseWhy

initFields = [fldSpCode, fldSrcTab, fldSrcFID, fldSFID, fldEOID, fldUse, fldUseWhy, fldDateCalc, fldDateFlag, fldRA,
              fldSFRACalc, fldRAFlag, fldFeatID, fldGrpID]
initDissList = [f.Name for f in initFields]

# not using these
# fldIsDup, fldRev, fldComments
# Additional fields for automation
# fldRaScore = Field('raScore', 'SHORT', '') # Quality score based on Representation Accuracy
# fldDateScore = Field('dateScore', 'SHORT', '') # Quality score based on date
# fldPQI = Field('pqiScore', 'SHORT', '') # Composite quality score ("Point Quality Index")
# fldGrpUse = Field('grpUse', 'LONG', '') # Identifies highest quality records in group (1) versus all other records (0)
# addFields = [fldRaScore, fldDateScore, fldPQI, fldGrpUse]



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


def GetElapsedTime(t1, t2):
   """Gets the time elapsed between the start time (t1) and the finish time (t2)."""
   delta = t2 - t1
   (d, m, s) = (delta.days, delta.seconds / 60, delta.seconds % 60)
   (h, m) = (m / 60, m % 60)
   deltaString = '%s days, %s hours, %s minutes, %s seconds' % (str(d), str(h), str(m), str(s))
   return deltaString


def printMsg(msg):
   arcpy.AddMessage(msg)
   print(msg)
   return


def printWrng(msg):
   arcpy.AddWarning(msg)
   print('Warning: ' + msg)
   return


def printErr(msg):
   arcpy.AddError(msg)
   print('Error: ' + msg)
   return


def ProjectToMatch(fcTarget, csTemplate):
   """Project a target feature class to match the coordinate system of a template dataset"""
   # Get the spatial reference of your target and template feature classes
   srTarget = arcpy.Describe(fcTarget).spatialReference  # This yields an object, not a string
   srTemplate = arcpy.Describe(csTemplate).spatialReference

   # Get the geographic coordinate system of your target and template feature classes
   gcsTarget = srTarget.GCS  # This yields an object, not a string
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
         arcpy.Project_management(fcTarget, fcTarget_prj, srTemplate)
      else:
         printMsg('Datums do not match; re-projecting with geographic transformation')
         # Get the list of applicable geographic transformations
         # This is a stupid long list
         transList = arcpy.ListTransformations(srTarget, srTemplate)
         # Extract the first item in the list, assumed the appropriate one to use
         geoTrans = transList[0]
         # Now perform reprojection with geographic transformation
         arcpy.Project_management(fcTarget, fcTarget_prj, srTemplate, geoTrans)
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
      printMsg('Working on "%s" field...' % fld)
      fldObject = arcpy.ListFields(FromTab, fld)[0]
      fldDict = TabToDict(FromTab, fldFromJoin, fld)
      printMsg('Established data dictionary.')
      expression = 'getFldVal(!%s!, %s)' % (fldToJoin, fldDict)
      srcFields = arcpy.ListFields(ToTab, fld)
      if len(srcFields) == 0:
         arcpy.AddField_management(ToTab, fld, fldObject.type, '', '', fldObject.length)
      printMsg('Calculating...')
      arcpy.CalculateField_management(ToTab, fld, expression, 'PYTHON', codeblock)
      printMsg('"%s" field done.' % fld)
   return ToTab


def SpatialCluster(inFeats, sepDist, fldGrpID='grpID'):
   '''Clusters features based on specified search distance. Features within twice the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   sepDist = The search distance to use for clustering.
   fldGrpID = The desired name for the output grouping field. If not specified, it will be "grpID".'''

   # set sepDist
   sd0 = sepDist.split(" ")
   if len(sd0) == 2:
      sepDist = str(int(sd0[0]) / 2) + " " + sd0[1]
   else:
      sepDist = str(int(sd0[0]) / 2)

   # Initialize trash items list
   trashList = []
   # Unique ID (OBJECT/FID)
   a = arcpy.Describe(inFeats).Fields
   for a1 in a:
      if a1.Type == 'OID':
         fldID = str(a1.Name)
         break

   # Delete the GrpID field from the input features, if it already exists.
   try:
      arcpy.DeleteField_management(inFeats, fldGrpID)
   except:
      pass

   # Buffer input features
   printMsg('Buffering input features')
   outBuff = scratchGDB + os.sep + 'outBuff'
   arcpy.Buffer_analysis(inFeats, outBuff, sepDist, '', '', 'ALL')
   trashList.append(outBuff)

   # Explode multipart  buffers
   printMsg('Exploding buffers')
   explBuff = scratchGDB + os.sep + 'explBuff'
   arcpy.MultipartToSinglepart_management(outBuff, explBuff)
   trashList.append(explBuff)

   # Add and populate grpID field in buffers
   printMsg('Populating grouping field in buffers')
   arcpy.AddField_management(explBuff, fldGrpID, 'LONG')
   arcpy.CalculateField_management(explBuff, fldGrpID, '!OBJECTID!', 'PYTHON')

   # Spatial join buffers with input features
   printMsg('Performing spatial join between buffers and input features')
   joinFeats = scratchGDB + os.sep + 'joinFeats'
   arcpy.SpatialJoin_analysis(inFeats, explBuff, joinFeats, 'JOIN_ONE_TO_ONE', 'KEEP_ALL', '', 'WITHIN')
   trashList.append(joinFeats)

   # Join grpID field to input features
   # This employs a custom function because arcpy is stupid slow at this
   JoinFields(inFeats, fldID, joinFeats, 'TARGET_FID', [fldGrpID])
   # arcpy.JoinField_management(inFeats, fldID, joinFeats, 'TARGET_FID', [fldGrpID])

   # Cleanup: delete buffers, spatial join features
   garbagePickup(trashList)

   printMsg('Processing complete.')

   return inFeats


# internal spatial clustering function over network dataset
def SpatialClusterNetwork(species_pt, species_ln, species_py, flowlines, catchments, network, dams, sep_dist, snap_dist,
                          output_lines):
   '''Clusters features based on specified search distance across a linear network dataset.
   Features within the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   sepDist = The distance with which to group features
   Adapted from script by Molly Moore, PANHP'''

   # env and extensions
   arcpy.env.workspace = scratchGDB
   arcpy.CheckOutExtension("Network")
   arcpy.env.qualifiedFieldNames = False

   # create empty list to store converted point layers for future merge
   species_lyrs = []

   # convert multipart points to singlepart
   if species_pt:
      pts = arcpy.MultipartToSinglepart_management(species_pt, "pts")
      species_lyrs.append(pts)

   # convert line and polygon data to vertices
   if species_ln:
      lns = arcpy.FeatureVerticesToPoints_management(species_ln, "lns", "ALL")
      species_lyrs.append(lns)

   if species_py:
      pys = arcpy.FeatureVerticesToPoints_management(species_py, "polys", "ALL")
      species_lyrs.append(pys)

   # merge the point layers together
   species_pt = arcpy.Merge_management(species_lyrs, "species_pt")

   # calculate separation distance to be used in tools. use half of original minus
   # 1 to account for 1 meter buffer and overlapping buffers
   sep_dist = int(sep_dist)
   sep_dist = (sep_dist / 2) - 2

   # create temporary unique id for use in join field later
   i = 1
   fieldnames = [field.name for field in arcpy.ListFields(species_pt)]
   if 'temp_join_id' not in fieldnames:
      arcpy.AddField_management(species_pt, "temp_join_id", "LONG")
      with arcpy.da.UpdateCursor(species_pt, "temp_join_id") as cursor:
         for row in cursor:
            row[0] = i
            cursor.updateRow(row)
            i += 1

   # delete identical points with tolerance to increase speed
   arcpy.DeleteIdentical_management(species_pt, [fldFeatID.Name, "Shape"], "35 Meters")

   arcpy.AddMessage("Creating service area line layer")
   # create service area line layer
   service_area_lyr = arcpy.na.MakeServiceAreaLayer(network, "service_area_lyr", "Length", "TRAVEL_FROM", sep_dist,
                                                    polygon_type="NO_POLYS", line_type="TRUE_LINES", overlap="OVERLAP")
   service_area_lyr = service_area_lyr.getOutput(0)
   subLayerNames = arcpy.na.GetNAClassNames(service_area_lyr)
   facilitiesLayerName = subLayerNames["Facilities"]
   serviceLayerName = subLayerNames["SALines"]
   arcpy.na.AddLocations(service_area_lyr, facilitiesLayerName, species_pt, "", snap_dist)
   arcpy.na.Solve(service_area_lyr)
   pyvers = sys.version_info.major
   if pyvers < 3:
      lines = arcpy.mapping.ListLayers(service_area_lyr, serviceLayerName)[0]
   else:
      lines = service_area_lyr.listLayers(serviceLayerName)[0]
   flowline_clip = arcpy.CopyFeatures_management(lines, "service_area")

   arcpy.AddMessage("Buffering service area flowlines")
   # buffer clipped service area flowlines by 1 meter
   flowline_buff = arcpy.Buffer_analysis(flowline_clip, "flowline_buff", "1 Meter", "FULL", "ROUND")

   arcpy.AddMessage("Dissolving service area polygons")
   # dissolve flowline buffers
   flowline_diss = arcpy.Dissolve_management(flowline_buff, "flowline_diss", multi_part="SINGLE_PART")

   # separate buffered flowlines at dams
   if dams:
      # buffer dams by 1.1 meters
      dam_buff = arcpy.Buffer_analysis(dams, "dam_buff", "1.1 Meter", "FULL", "FLAT")
      # split flowline buffers at dam buffers by erasing area of dam
      flowline_erase = arcpy.Erase_analysis(flowline_diss, dam_buff, "flowline_erase")
      multipart_input = flowline_erase
   else:
      multipart_input = flowline_diss

   # multi-part to single part to create unique polygons
   single_part = arcpy.MultipartToSinglepart_management(multipart_input, "single_part")

   # create unique group id
   group_id = fldGrpID.Name  # unique to this toolbox
   arcpy.AddField_management(single_part, group_id, "LONG")
   num = 1
   with arcpy.da.UpdateCursor(single_part, group_id) as cursor:
      for row in cursor:
         row[0] = num
         cursor.updateRow(row)
         num += 1

   # join group id of buffered flowlines to closest points
   s_join = arcpy.SpatialJoin_analysis(target_features=species_pt, join_features=single_part,
                                       out_feature_class="s_join", join_operation="JOIN_ONE_TO_ONE",
                                       join_type="KEEP_ALL", match_option="CLOSEST", search_radius=snap_dist,
                                       distance_field_name="")
   # join field to original dataset
   join_field = [field.name for field in arcpy.ListFields(s_join)]
   join_field = join_field[-1]
   arcpy.JoinField_management(species_pt, "temp_join_id", s_join, "temp_join_id", join_field)

   # delete null groups to get rid of observations that were beyond snap_dist
   with arcpy.da.UpdateCursor(species_pt, join_field) as cursor:
      for row in cursor:
         if row[0] is None:
            cursor.deleteRow()

   arcpy.AddMessage("Joining COMID")
   # join species_pt layer with catchments to assign COMID
   sp_join = arcpy.SpatialJoin_analysis(species_pt, catchments, "sp_join", "JOIN_ONE_TO_ONE", "KEEP_COMMON", "",
                                        "INTERSECT")
   sp_join = arcpy.DeleteIdentical_management(sp_join, [group_id, "FEATUREID"])
   if len(arcpy.ListFields(sp_join, "COMID")) == 0:
      arcpy.AddField_management(sp_join, "COMID", "LONG")
      with arcpy.da.UpdateCursor(sp_join, ["FEATUREID", "COMID"]) as cursor:
         for row in cursor:
            row[1] = str(row[0])
            cursor.updateRow(row)

   # obtain list of duplicate COMID because these are reaches assigned to multiple groups
   freq = arcpy.Frequency_analysis(sp_join, "freq", "COMID")
   dup_comid = []
   with arcpy.da.SearchCursor(freq, ["FREQUENCY", "COMID"]) as cursor:
      for row in cursor:
         if row[0] > 1:
            dup_comid.append(row[1])

   arcpy.AddMessage("Resolving same reaches assigned to different groups")
   # get all groups within duplicate reaches and assign them to a single group
   sp_join_lyr = arcpy.MakeFeatureLayer_management(sp_join, "sp_join_lyr")
   if dup_comid:
      for dup in dup_comid:
         arcpy.SelectLayerByAttribute_management(sp_join_lyr, "NEW_SELECTION", "COMID = {0}".format(dup))
         combine_groups = []
         with arcpy.da.SearchCursor(sp_join_lyr, [group_id]) as cursor:
            for row in cursor:
               combine_groups.append(row[0])
         arcpy.SelectLayerByAttribute_management(sp_join_lyr, "NEW_SELECTION", fldGrpID.Name + " IN ({0})".format(
            ','.join(str(x) for x in combine_groups)))
         with arcpy.da.UpdateCursor(sp_join_lyr, [group_id]) as cursor:
            for row in cursor:
               row[0] = num
               cursor.updateRow(row)
         num += 1

   # clear selection on layer
   arcpy.SelectLayerByAttribute_management(sp_join_lyr, "CLEAR_SELECTION")

   # get list of COMID values for export of flowlines
   with arcpy.da.SearchCursor(sp_join_lyr, "COMID") as cursor:
      comid = sorted({row[0] for row in cursor})
   comid = list(set(comid))

   # join attributes to flowlines
   expression = 'COMID IN ({0})'.format(','.join(str(x) for x in comid))
   flowlines_lyr = arcpy.MakeFeatureLayer_management(flowlines, "flowlines_lyr", expression)
   arcpy.AddJoin_management(flowlines_lyr, "COMID", sp_join, "COMID")

   arcpy.env.qualifiedFieldNames = False

   # export presence flowlines
   flowlines_lyr = arcpy.CopyFeatures_management(flowlines_lyr, "flowlines_lyr")
   # reduce fields
   myfields = ['COMID', 'FEATUREID', 'SOURCEFC'] + initDissList
   # create an empty field mapping object
   mapS = arcpy.FieldMappings()
   # for each field, create an individual field map, and add it to the field mapping object
   for field in myfields:
      arcpy.AddMessage("field: " + field)
      try:
         map = arcpy.FieldMap()
         map.addInputField(flowlines_lyr, field)
         mapS.addFieldMap(map)
      except:
         next
   arcpy.FeatureClassToFeatureClass_conversion(flowlines_lyr, os.path.dirname(output_lines),
                                               os.path.basename(output_lines), "#", mapS)

   # append group IDs to original datasets
   if species_py:
      species_pt = arcpy.DeleteIdentical_management(species_pt, [fldFeatID.Name, group_id])
      JoinFields(species_py, fldFeatID.Name, species_pt, fldFeatID.Name, [fldGrpID.Name])

   # delete temporary fields and datasets
   # arcpy.Delete_management("in_memory")
   return species_py


def tbackInLoop():
   '''Standard error handling routing to add to bottom of scripts'''
   tb = sys.exc_info()[2]
   tbinfo = traceback.format_tb(tb)[0]
   pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n " + str(sys.exc_info()[1])
   msgs = arcpy.GetMessages(1)
   msgList = [pymsg, msgs]

   # printWrng(msgs)
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
   name = path[(path.rindex("/") + 1):len(path)]
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
def GetOverlapping(inList, outPolys, summFlds=None, dissolve=False):
   '''Internal function for MergeData. Generates all unique polygons from list of polygon FCs.'''

   polyID = 'uniqID_poly'
   if len(inList) > 1:
      print('Merging all datasets...')
      m = arcpy.Merge_management(inList, scratchGDB + os.sep + 'merged0')
      m0 = arcpy.MultipartToSinglepart_management(m, scratchGDB + os.sep + 'merged0_single')
   else:
      print('Converting to single-part...')
      m0 = arcpy.MultipartToSinglepart_management(inList[0], scratchGDB + os.sep + 'merged0_single')
   upoly = arcpy.CountOverlappingFeatures_analysis(m0, scratchGDB + os.sep + 'upoly')
   arcpy.AddField_management(upoly, polyID, 'LONG')
   arcpy.CalculateField_management(upoly, polyID, '!OBJECTID!')
   # check if any overlaps
   maxct = max([a[0] for a in arcpy.da.SearchCursor(upoly, "COUNT_")])

   if maxct > 1:
      ct1 = arcpy.FeatureToPoint_management(upoly, scratchGDB + os.sep + 'ct1', point_location="INSIDE")
      sj0 = arcpy.SpatialJoin_analysis(ct1, m0, scratchGDB + os.sep + 'sj0', "JOIN_ONE_TO_MANY", "KEEP_ALL", match_option="WITHIN")
      # Generate one polygon for each overlap section from any dataset
      allpoly = arcpy.SpatialJoin_analysis(upoly, sj0, scratchGDB + os.sep + 'allpoly', "JOIN_ONE_TO_MANY", "KEEP_ALL", match_option="INTERSECT")
      if summFlds:
         print('Returning `flat` polygons with summarized fields...')
         summ0 = arcpy.Statistics_analysis(allpoly, scratchGDB + os.sep + 'summ0', summFlds, polyID)
         arcpy.JoinField_management(upoly, polyID, summ0, polyID)
         arcpy.CopyFeatures_management(upoly, outPolys)
      else:
         print('Returning all polygons (duplicated in areas of overlap)...')
         arcpy.CopyFeatures_management(allpoly, outPolys)
   else:
      # no overlaps
      print('No overlaps, returning merged single-part feature class...')
      arcpy.SpatialJoin_analysis(m0, upoly, outPolys, "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="ARE_IDENTICAL_TO")

   # outPolys has fields uniqID_poly and COUNT_.

   return outPolys




# used in MergeData: deprecated once SummarizeOverlapping is done.
def xMarkSpatialDuplicates(inPolys, fldDateCalc='sdm_date', fldSFRA='tempSFRACalc', fldUse='sdm_use',
                          fldUseWhy='sdm_use_why', fldRaScore='sdm_ra'):
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
      printWrng(
         "Some '" + fldSFRA + "' values not in allowed RA values. These will receive an '" + fldRaScore + "' value of 0.")
      # return?

   fldSDC = 'sdc'
   # Get initial record count
   arcpy.MakeFeatureLayer_management(inPolys, 'lyrPolys')
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

   print('Updating ' + fldUse + ' column...')

   where_clause = "%s = 0" % fldSDC
   arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", where_clause)
   numPolys = countFeatures('lyrPolys')

   printMsg('Identifying spatial duplicates...')
   while numPolys > 0:
      id = min(unique_values('lyrPolys', idCol))
      # printMsg('Working on ID %s' %id)

      # Select the next un-assigned record
      where_clause1 = "%s = %s" % (idCol, id)
      arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", where_clause1)
      arcpy.SelectLayerByLocation_management('lyrPolys', "ARE_IDENTICAL_TO", 'lyrPolys',
                                             selection_type="ADD_TO_SELECTION")
      arcpy.CalculateField_management('lyrPolys', fldSDC, 1, 'PYTHON')  # has been checked; set to 1

      # Count the records
      numPolys = countFeatures('lyrPolys')

      if numPolys == 1:
         # set isDup to 0
         arcpy.CalculateField_management('lyrPolys', fldUse, 1, 'PYTHON')
      else:
         # set all selected to 0 to start
         arcpy.CalculateField_management('lyrPolys', fldUse, 0, 'PYTHON')
         arcpy.CalculateField_management('lyrPolys', fldUseWhy, '"spatial duplicate"', 'PYTHON')

         # Find the maximum RA value
         raList = unique_values('lyrPolys', fldRaScore)
         maxRa = max(raList)

         # Unselect any records where the RA is less than the maximum
         where_clause2 = "%s < %s" % (fldRaScore, maxRa)
         arcpy.SelectLayerByAttribute_management('lyrPolys', "REMOVE_FROM_SELECTION", where_clause2)

         # Find the maximum standard date value
         dateList = unique_values('lyrPolys', fldDateCalc)
         maxDate = max(dateList)

         # Unselect any records where the date is less than the maximum
         where_clause2 = "%s < '%s'" % (fldDateCalc, maxDate)
         arcpy.SelectLayerByAttribute_management('lyrPolys', "REMOVE_FROM_SELECTION", where_clause2)

         # Count the remaining records, assign 1 to lowest ID number
         numPolys = countFeatures('lyrPolys')
         if numPolys == 1:
            arcpy.CalculateField_management('lyrPolys', fldUse, 1, 'PYTHON')
         else:
            idList = unique_values('lyrPolys', idCol)
            minID = min(idList)
            where_clause2 = "%s <> %s" % (idCol, minID)
            arcpy.SelectLayerByAttribute_management('lyrPolys', "REMOVE_FROM_SELECTION", where_clause2)
            arcpy.CalculateField_management('lyrPolys', fldUse, 1, 'PYTHON')
         arcpy.CalculateField_management('lyrPolys', fldUseWhy, '""', "PYTHON")

      # select remaining unassigned polys
      where_clause = "%s = 0" % fldSDC
      arcpy.SelectLayerByAttribute_management('lyrPolys', "NEW_SELECTION", where_clause)
      numPolys = countFeatures('lyrPolys')

   # Get final record count
   numPolysFinal = countFeatures(inPolys)
   arcpy.SelectLayerByAttribute_management('lyrPolys', "CLEAR_SELECTION")
   arcpy.DeleteField_management('lyrPolys', fldSDC)

   return inPolys


def fc2df(feature_class, field_list, skip_nulls=True):
   """
   Load data into a Pandas Data Frame for subsequent analysis.
   :param feature_class: Input ArcGIS Feature Class.
   :param field_list: Fields for input.
   :return: Pandas DataFrame object.
   """
   from pandas import DataFrame
   if not skip_nulls:
      return DataFrame(
         arcpy.da.FeatureClassToNumPyArray(
            in_table=feature_class,
            field_names=field_list,
            skip_nulls=False,
            null_value=-99999
         )
      )
   else:
      return DataFrame(
         arcpy.da.FeatureClassToNumPyArray(
            in_table=feature_class,
            field_names=field_list,
            skip_nulls=True
         )
      )


def df2tab(df, outTable):
   """
   Create an ArcGIS table from a Pandas Data Frame (generally for joins)
   :param df: Input pandas DataFrame
   :param outTable: Name of output table
   :return: outTable
   """
   import numpy as np
   x = np.array(np.rec.fromrecords(df.values))
   names = df.dtypes.index.tolist()
   names = [str(n) for n in names]
   x.dtype.names = tuple(names)
   return arcpy.da.NumPyArrayToTable(x, outTable)



# end