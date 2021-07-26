# Helper functions for python toolbox

import arcpy
import datetime
import os
import re
import sys
import traceback
import csv
from datetime import datetime as datetime

arcpy.CheckOutExtension("Spatial")
scratchGDB = arcpy.env.scratchFolder + os.sep + 'sdmPresencePreProc.gdb'  # r'C:\David\scratch\sdmPresencePreProc.gdb'
if not os.path.exists(scratchGDB):
   arcpy.CreateFileGDB_management(os.path.dirname(scratchGDB), os.path.basename(scratchGDB))
curr_dir = os.path.dirname(os.path.abspath(__file__))

### Define the fields to add
class Field:
   def __init__(self, Name='', Type='', Length=''):
      self.Name = Name
      self.Type = Type
      self.Length = Length

# Initial fields for editing
fldSpCode = Field('sp_code', 'TEXT', 20)  # Code to identify species. Example: 'clemaddi'. If subspecies, use trinomial
fldSrcTab = Field('src_table', 'TEXT', 50)  # Code to identify source dataset. Example: 'biotics'
fldSrcFID = Field('src_fid', 'LONG', '')  # original source table FID (auto-populated)
fldSFID = Field('src_featid', 'LONG', '')  # original feature's SFID or similar (Source feature ID in Biotics)
fldEOID = Field('src_grpid', 'TEXT', 50)  # original group ID (EO ID in biotics)
fldUse = Field('sdm_use', 'SHORT', '')  # Binary: Eligible for use in model training (1) or not (0)
fldUseWhy = Field('sdm_use_why', 'TEXT', 1000)  # Comments on eligibility for use
fldDateCalc = Field('sdm_date', 'TEXT', 10)  # Date in standardized yyyy-mm-dd format
fldDateFlag = Field('sdm_date_flag', 'SHORT', '')  # Flag uncertain year. 0 = certain; 1 = uncertain
fldRA = Field('sdm_ra', 'SHORT', '')  # Source feature representation accuracy
fldSFRACalc = Field('tempSFRACalc', 'TEXT', 20)  # for storing original RA column values for editing
fldRAFlag = Field('sdm_ra_flag', 'SHORT', '')  # Flag for editing. 0 = okay; 1 = needs edits; 2 = edits done
fldFeatID = Field('sdm_featid', 'LONG', '')  # new unique id by polygon
fldGrpID = Field('sdm_grpid', 'TEXT', 50)  # new unique id by group

# not using these
# fldIsDup, fldRev, fldComments
# Additional fields for automation
# fldRaScore = Field('raScore', 'SHORT', '') # Quality score based on Representation Accuracy
# fldDateScore = Field('dateScore', 'SHORT', '') # Quality score based on date
# fldPQI = Field('pqiScore', 'SHORT', '') # Composite quality score ("Point Quality Index")
# fldGrpUse = Field('grpUse', 'LONG', '') # Identifies highest quality records in group (1) versus all other records (0)
# fldComments = Field('revComments', 'TEXT', 250) # Field for review/editing comments; dropping in favor of UseWhy
# addFields = [fldRaScore, fldDateScore, fldPQI, fldGrpUse]

# Field lists
initFields = [fldSpCode, fldSrcTab, fldSrcFID, fldSFID, fldEOID, fldUse, fldUseWhy, fldDateCalc, fldDateFlag, fldRA,
              fldSFRACalc, fldRAFlag, fldFeatID, fldGrpID]
initDissList = [f.Name for f in initFields]
initFieldsFull = [[f.Name, f.Type, f.Name, f.Length] for f in initFields]

# Date calculation logic. Used in AddInitFields
def getStdDate(Date):
   # Import regular expressions module
   import re
   
   # Set up some regular expressions for pattern matching dates
   p1 = re.compile(r'^[1-2][0-9][0-9][0-9]-[0-1][0-9]-[0-9][0-9]$') # yyyy-mm-dd
   p2 = re.compile(r'^[1-2][0-9][0-9][0-9]-[0-1][0-9]$') # yyyy-mm
   p3 = re.compile(r'^[1-2][0-9][0-9][0-9]-?$') # yyyy or yyyy-
   p4 = re.compile(r'^[0-9][0-9]?/[0-9][0-9]?/[1-2][0-9][0-9][0-9]$') # m/d/yyyy or mm/dd/yyyy
   p4m = re.compile(r'^[0-9][0-9]?/') # to extract month
   p4d = re.compile(r'/[0-9][0-9]?/') # to extract day

   if type(Date) == datetime:
      # arcgis date fields are datetime types
      Date = str(Date.date())
   else:
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
      # Try to get any four digits in a row
      y0 = re.findall('(?<!\d)\d{4}(?!\d)', Date)[-1:]
      if len(y0) == 0:
         yyyy = '0000'
      else:
         yyyy = y0[0]
      mm = '00'
      dd = '00'
   
   yyyymmdd = yyyy + '-' + mm + '-' + dd
   return yyyymmdd


def copyFld(lyr, fieldIn, fieldOut):
   """Copy values from one field to another new field"""
   with arcpy.da.UpdateCursor(lyr, [fieldIn, fieldOut]) as cursor:
      for row in cursor:
         row[1] = row[0]
         cursor.updateRow(row)


def countFeatures(features):
   """Gets count of features"""
   count = int((arcpy.GetCount_management(features)).getOutput(0))
   return count


def garbagePickup(trashList):
   """Deletes Arc files in list, with error handling. Argument must be a list."""
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


def JoinFields(ToTab, fldToJoin, FromTab, fldFromJoin, addFields):
   """An alternative to arcpy's JoinField_management.
   Note that this method is best for small 'FromTab' tables and one-two join fields.

   ToTab = The table to which fields will be added
   fldToJoin = The key field in ToTab, used to match records in FromTab
   FromTab = The table from which fields will be copied
   fldFromJoin = the key field in FromTab, used to match records in ToTab
   addFields = the list of fields to be added"""

   def getFldVal(srcID, fldDict):
      try:
         fldVal = fldDict[srcID]
      except:
         fldVal = None
      return fldVal

   # set up dictionary
   codeDict = {}
   ls = [fldFromJoin] + addFields
   num = list(range(1, len(addFields)+1))
   numt = [str(n) for n in num]
   text = "sc[" + ("], sc[").join(numt) + "]"
   with arcpy.da.SearchCursor(FromTab, ls) as sc:
      for row in sc:
         key = sc[0]
         codeDict[key] = eval(text)

   fldTypes = [a for a in arcpy.ListFields(FromTab) if a.name in addFields]
   existFld = [f.name for f in arcpy.ListFields(ToTab)]
   toAdd = [a for a in fldTypes if a.name not in existFld]
   # TODO: need to translate field types to get this to work
   # if len(toAdd) > 0:
   #   arcpy.AddFields_management(ToTab, [[a.name, a.type, a.name, a.length] for a in toAdd])
   for f in toAdd:
      arcpy.AddField_management(ToTab, f.name, f.type, '', '', f.length)

   # Join fields
   ls = [fldToJoin] + addFields
   if len(addFields) > 1:
      with arcpy.da.UpdateCursor(ToTab, ls) as cursor:
         for row in cursor:
            vals = getFldVal(row[0], codeDict)
            if vals:
               vals2 = list(vals)
               for n in num:
                  row[n] = vals2[n-1]
               cursor.updateRow(row)
   else:
      # one field only
      with arcpy.da.UpdateCursor(ToTab, ls) as cursor:
         for row in cursor:
            row[1] = getFldVal(row[0], codeDict)
            cursor.updateRow(row)
   return ToTab


def SpatialCluster(inFeats, sepDist, fldGrpID='grpID'):
   """Clusters features based on specified search distance. Features within twice the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   sepDist = The search distance to use for clustering.
   fldGrpID = The desired name for the output grouping field. If not specified, it will be "grpID"."""

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
   # arcpy.CalculateField_management(explBuff, fldGrpID, '!OBJECTID!', 'PYTHON')
   copyFld(explBuff, 'OBJECTID', fldGrpID)

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
   """Clusters features based on specified search distance across a linear network dataset.
   Features within the search distance of each other will be assigned to the same group.
   :param species_pt, species_ln, species_py = The input features to group
   :param sepDist = The distance with which to group features
   Adapted from script by Molly Moore, PANHP"""

   # testing
   # network = r'F:\David\GIS_data\NHDPlus_HR\VA_HydroNetHR.gdb\HydroNet\HydroNet_ND'
   # output_lines = "testlines"
   #

   # env and extensions
   arcpy.env.workspace = scratchGDB
   arcpy.CheckOutExtension("Network")
   arcpy.env.qualifiedFieldNames = False

   # create empty list to store converted point layers for future merge
   species_lyrs = []

   arcpy.AddMessage('Generating points to use in network analysis...')
   # This process also attributes points with flowline IDs (NHDPlusID in NHDPlusHR),
   #  using catchments (NOT nearest flowline).
   if species_pt:
      arcpy.MultipartToSinglepart_management(species_pt, "pts0")
      pts = arcpy.Identity_analysis('pts0', catchments, 'ptcats', "NO_FID")
      species_lyrs.append(pts)

   # convert lines to by-catchment endpoint vertices
   if species_ln:
      arcpy.Identity_analysis(species_ln, catchments, 'lincats', "NO_FID")
      lns = arcpy.FeatureVerticesToPoints_management('lincats', "lns", "BOTH_ENDS")
      species_lyrs.append(lns)

   # convert polygons to by-catchment, subdivided-polygon centroids
   if species_py:
      arcpy.Identity_analysis(species_py, catchments, 'polycats', "NO_FID")
      # Target area size calculated as square of snap-distance (default would be 10,000 sq. meters)
      arcpy.SubdividePolygon_management("polycats", "polycats_subd", "EQUAL_AREAS",
                                        target_area=float(snap_dist)**2, subdivision_type="STACKED_BLOCKS")
      pys = arcpy.FeatureToPoint_management('polycats_subd', 'polys', "INSIDE")
      # pys = arcpy.FeatureVerticesToPoints_management(species_py, "polys", "ALL")
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

   # delete identical points
   arcpy.DeleteIdentical_management(species_pt, "Shape")

   arcpy.AddMessage("Creating service area line layer...")
   pyvers = sys.version_info.major
   if pyvers < 3:
      # create service area line layer for ArcMap
      service_area_lyr = arcpy.na.MakeServiceAreaLayer(network, "service_area_lyr", "Length", "TRAVEL_FROM", sep_dist,
                                                       polygon_type="NO_POLYS", line_type="TRUE_LINES",
                                                       overlap="OVERLAP", restriction_attribute_name="#")
      # Note: Restriction attribute name = "#" is necessary for networks with standard restrictions in place.
   else:
      # ArcGIS Pro: old MakeServiceAreaLayer call would work, but is deprecated, see:
      # (https://pro.arcgis.com/en/pro-app/tool-reference/network-analyst/make-service-area-layer.htm)
      tm = arcpy.na.TravelMode(arcpy.na.GetTravelModes(network)["Standard"])
      tm.name = "noRestrict"
      # Note: This removes all travel restrictions along network
      tm.restrictions = []
      service_area_lyr = arcpy.na.MakeServiceAreaAnalysisLayer(network, "service_area_lyr", tm, "FROM_FACILITIES",
                                                               sep_dist, output_type="LINES",
                                                               geometry_at_overlaps="OVERLAP")
   service_area_lyr = service_area_lyr.getOutput(0)
   subLayerNames = arcpy.na.GetNAClassNames(service_area_lyr)
   facilitiesLayerName = subLayerNames["Facilities"]
   serviceLayerName = subLayerNames["SALines"]
   arcpy.na.AddLocations(service_area_lyr, facilitiesLayerName, species_pt, "", snap_dist)
   arcpy.na.Solve(service_area_lyr, "SKIP")
   if pyvers < 3:
      lines = arcpy.mapping.ListLayers(service_area_lyr, serviceLayerName)[0]
   else:
      lines = service_area_lyr.listLayers(serviceLayerName)[0]
   flowline_clip = arcpy.CopyFeatures_management(lines, "service_area")

   arcpy.AddMessage("Buffering service area flowlines...")
   # buffer clipped service area flowlines by 1 meter, dissolved all
   flowline_buff = arcpy.Buffer_analysis(flowline_clip, "flowline_buff", "1 Meter", "FULL", "ROUND", "ALL")

   # separate buffered flowlines at dams
   if dams:
      arcpy.AddMessage("Splitting service areas at dam locations...")
      # buffer dams by 1.1 meters
      dams0 = arcpy.MakeFeatureLayer_management(dams)
      arcpy.SelectLayerByLocation_management(dams0, "INTERSECT", flowline_buff)
      if int(arcpy.GetCount_management(dams0)[0]) > 0:
         dam_buff = arcpy.Buffer_analysis(dams0, "dam_buff", "1.1 Meter", "FULL", "FLAT")
         # split flowline buffers at dam buffers by erasing area of dam
         flowline_erase = arcpy.Erase_analysis(flowline_buff, dam_buff, "flowline_erase")
         multipart_input = flowline_erase
      else:
         multipart_input = flowline_buff
   else:
      multipart_input = flowline_buff

   # multi-part to single part to create unique polygons
   single_part = arcpy.MultipartToSinglepart_management(multipart_input, "single_part")

   # create unique group id
   group_id = fldGrpID.Name  # unique to this toolbox
   if group_id not in [a.name for a in arcpy.ListFields(single_part)]:
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
   # join_field = [field.name for field in arcpy.ListFields(s_join)]
   # join_field = join_field[-1]
   arcpy.JoinField_management(species_pt, "temp_join_id", s_join, "temp_join_id", group_id)

   # delete null groups to get rid of observations that were beyond snap_dist
   with arcpy.da.UpdateCursor(species_pt, group_id) as cursor:
      for row in cursor:
         if row[0] is None:
            cursor.deleteRow()

   arcpy.AddMessage("Joining flowline ID...")
   flow_ID = 'NHDPlusID'   # previously COMID
   sp_join = arcpy.CopyFeatures_management(species_pt, 'sp_join')
   sp_join = arcpy.DeleteIdentical_management(sp_join, [group_id, flow_ID])

   # OLD METHOD: join species_pt layer with catchments to assign COMID
   # sp_join = arcpy.SpatialJoin_analysis(species_pt, catchments, "sp_join", "JOIN_ONE_TO_ONE", "KEEP_COMMON", "",
   #                                      "INTERSECT")
   # Below not used: NHDPlusID is only ID needed in NHDPlusHR
   # if len(arcpy.ListFields(sp_join, "COMID")) == 0:
   #    arcpy.AddField_management(sp_join, "COMID", "LONG")
   #    with arcpy.da.UpdateCursor(sp_join, ["FEATUREID", "COMID"]) as cursor:
   #       for row in cursor:
   #          row[1] = str(row[0])
   #          cursor.updateRow(row)

   # obtain list of duplicate COMID because these can be reaches assigned to multiple groups
   freq = arcpy.Frequency_analysis(sp_join, "freq", flow_ID)
   dup_comid = []
   with arcpy.da.SearchCursor(freq, ["FREQUENCY", flow_ID]) as cursor:
      for row in cursor:
         if row[0] > 1:
            dup_comid.append(row[1])

   # get all groups within duplicate reaches and assign them to a single group
   sp_join_lyr = arcpy.MakeFeatureLayer_management(sp_join, "sp_join_lyr")
   if dup_comid:
      arcpy.AddMessage("Resolving same reaches assigned to different groups")
      for dup in dup_comid:
         arcpy.SelectLayerByAttribute_management(sp_join_lyr, "NEW_SELECTION", flow_ID + " = {0}".format(dup))
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
   with arcpy.da.SearchCursor(sp_join_lyr, flow_ID) as cursor:
      comid = sorted({row[0] for row in cursor})
   comid = list(set(comid))

   # join attributes to flowlines
   expression = flow_ID + ' IN ({0})'.format(','.join(str(x) for x in comid))
   flowlines_lyr = arcpy.MakeFeatureLayer_management(flowlines, "flowlines_lyr", expression)
   arcpy.AddJoin_management(flowlines_lyr, flow_ID, sp_join, flow_ID)

   arcpy.env.qualifiedFieldNames = False

   # export presence flowlines
   flowlines_lyr = arcpy.CopyFeatures_management(flowlines_lyr, "flowlines_lyr")
   # reduce fields
   # myfields = ['COMID', 'FEATUREID', 'SOURCEFC'] + initDissList
   # NOTE: These are NHDPlusHR attributes
   myfields = [flow_ID, 'StreamOrde', 'Permanent_Identifier'] + initDissList
   # create an empty field mapping object
   mapS = arcpy.FieldMappings()
   # for each field, create an individual field map, and add it to the field mapping object
   for field in myfields:
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
      # species_pt = arcpy.DeleteIdentical_management(species_pt, [fldFeatID.Name, group_id])
      # JoinFields(species_py, fldFeatID.Name, species_pt, fldFeatID.Name, [fldGrpID.Name])
      arcpy.Statistics_analysis(species_pt, 'pt_join_py', [[fldGrpID.Name, 'COUNT']], [fldFeatID.Name, fldGrpID.Name])
      u = [a[0] for a in arcpy.da.SearchCursor('pt_join_py', fldFeatID.Name)]
      u2 = [str(a) for a in list(set(u)) if u.count(a) > 1]
      if len(u2) > 0:
         arcpy.Sort_management('pt_join_py', 'pt_join_py2', [['COUNT_' + fldGrpID.Name, 'Ascending']])
         printMsg('One or more features cover multiple occurrence groups (' + fldFeatID.Name + ' in [' + ','.join(u2) +
                  ']). The most common group ID among feature input points will be assigned to the polygon(s).')
         jn = 'pt_join_py2'
      else:
         jn = 'pt_join_py'
      arcpy.JoinField_management(species_py, fldFeatID.Name, jn, fldFeatID.Name, fldGrpID.Name)

   return species_py


def tbackInLoop():
   """Standard error handling routing to add to bottom of scripts"""
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
   """ Gets list of unique values in a field.
   Thanks, ArcPy Cafe! https://arcpy.wordpress.com/2012/02/01/create-a-list-of-unique-field-values/"""
   val = [r[0] for r in arcpy.da.SearchCursor(table, [field])]
   uv = list(set(val))
   return uv


def make_gdb(path):
   """ Creates a geodatabase if it doesn't exist"""
   path = path.replace("\\", "/")
   folder = os.path.dirname(path)
   name = make_gdb_name(os.path.basename(path).replace('.gdb', '')) + '.gdb'
   path = folder + '/' + name
   if not os.path.exists(path):
      try:
         arcpy.CreateFileGDB_management(folder, name)
      except:
         printMsg("Geodatabase '" + path + "' could not be created.")
         return False
      else:
         printMsg("Geodatabase '" + path + "' created.")
         return True
   else:
      printMsg("Geodatabase '" + path + "' already exists.")
      return True


def make_gdb_name(string):
   """Makes strings GDB-compliant"""
   while not string[0].isalpha():
      string = string[1:len(string)]
   nm = re.sub('[^A-Za-z0-9]+', '_', string)
   return nm


# used in MergeData
def GetOverlapping(inList, outPolys, summFlds=None):
   """Internal function for MergeData. Generates all unique polygons from list of one or more polygon FCs.
   If summFlds is provided, final dataset will be 'flat' (no overlap), with only ID, Count, and summary
   fields returned."""

   # unique polygon ID to assign to new 'flat' dataset
   polyID = 'uniqID_poly'
   if len(inList) > 1:
      print('Merging all datasets, converting to single-part...')
      m = arcpy.Merge_management(inList, scratchGDB + os.sep + 'merged0')
      m0 = arcpy.MultipartToSinglepart_management(m, scratchGDB + os.sep + 'merged0_single')
   else:
      print('Converting to single-part...')
      m0 = arcpy.MultipartToSinglepart_management(inList[0], scratchGDB + os.sep + 'merged0_single')

   upoly = arcpy.CountOverlappingFeatures_analysis(m0, scratchGDB + os.sep + 'upoly')
   arcpy.AddField_management(upoly, polyID, 'LONG')
   # arcpy.CalculateField_management(upoly, polyID, '!OBJECTID!')
   copyFld(upoly, 'OBJECTID', polyID)
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
      # still want dataset to include uniqID_poly and COUNT_ fields, so join here.
      arcpy.SpatialJoin_analysis(m0, upoly, outPolys, "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="ARE_IDENTICAL_TO")

   # outPolys has fields uniqID_poly and COUNT_.

   return outPolys


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