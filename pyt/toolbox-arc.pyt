# -*- coding: utf-8 -*-
"""
Created on Thu May 10 11:52:23 2018

@author: David Bucklin
"""
# This is the sdmPresencePreProc arctoolbox.
# Everything from here until class(Toolbox)
# is internal functions and field definitions

# TODOS (list by priority; remove when added)
# in line selection SpatialClusterNetwork, could choose highest RA/latest date for line/poly associations
# sep. dists., other info. could be stored in a metadata table
# Aquatic grouping tool:
"""
1. updates sdm_grp_id
2. Returns table of [unique COMID], feat occur attributes, [line geom], score, etc.
   - figure out how to select which feat occur attaches to which line (maybe just latest date of all related, or highest score).
3. update sdm_grp_id if necessary (if two groups share a line)
4. update sdm_use best as possible

overall need = GetLinesSimple integrate into grouping network - maybe just update with SDM_Tools from PA group.

Network should be NHDPlusv2
- possibly remove strord == 1
"""

import arcpy
import os, sys, traceback, re, pandas
from datetime import datetime as datetime

from arcpy.sa import *
from arcpy.na import *
arcpy.CheckOutExtension("Spatial")
#scratchGDB = arcpy.env.scratchGDB
scratchGDB = "in_memory"


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
   
def SpatialCluster (inFeats, sepDist, fldGrpID = 'grpID'):
   '''Clusters features based on specified search distance. Features within twice the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   sepDist = The search distance to use for clustering.
   fldGrpID = The desired name for the output grouping field. If not specified, it will be "grpID".'''
   
   # set sepDist
   sd0 = sepDist.split(" ")
   if len(sd0) == 2:
      sepDist = str(int(sd0[0])/2) + " " + sd0[1]
   else:
      sepDist = str(int(sd0[0])/2)
   
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
      arcpy.DeleteField_management (inFeats, fldGrpID)
   except:
      pass
      
   # Buffer input features
   printMsg('Buffering input features')
   outBuff = scratchGDB + os.sep + 'outBuff'
   arcpy.Buffer_analysis (inFeats, outBuff, sepDist, '', '', 'ALL')
   trashList.append(outBuff)
   
   # Explode multipart  buffers
   printMsg('Exploding buffers')
   explBuff = scratchGDB + os.sep + 'explBuff'
   arcpy.MultipartToSinglepart_management (outBuff, explBuff)
   trashList.append(explBuff)
   
   # Add and populate grpID field in buffers
   printMsg('Populating grouping field in buffers')
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
   #arcpy.JoinField_management(inFeats, fldID, joinFeats, 'TARGET_FID', [fldGrpID])

   # Cleanup: delete buffers, spatial join features
   garbagePickup(trashList)
   
   printMsg('Processing complete.')
   
   return inFeats
   

# internal spatial clustering function over network dataset
def SpatialClusterNetwork_old(inFeats, sepDist, network, barriers = "#", fldGrpID = 'grpID'):
   '''Clusters features based on specified search distance across a linear network dataset.
   Features within the search distance of each other will be assigned to the same group.
   inFeats = The input features to group
   sepDist = The distance with which to group features
   Adapted from script by Molly Moore, PANHP'''
   
   # from arcpy.na import *
   netName = arcpy.Describe(network).name
   
   # set environment settings
   arcpy.CheckOutExtension("Network")
   arcpy.env.overwriteOutput = True
   
   #calculate separation distance to be used in tools. use half of original minus
   #1 to account for 1 meter buffer and overlapping buffers
   #sepDist = int(sepDist)
   #sepDist = (sepDist/2)-1
   
   sd0 = sepDist.split(" ")
   if len(sd0) == 2:
      # sepDist = str(int(sd0[0])/2 - 1) + " " + sd0[1] # cannot handle units text
      sepDist = str(int(sd0[0])/2 - 1)
   else:
      sepDist = str(int(sd0[0])/2 - 1)
   
   #create temporary unique id for use in join field later
   i=1
   fieldnames = [field.name for field in arcpy.ListFields(inFeats)]
   if 'temp_join_id' not in fieldnames:
       arcpy.AddField_management(inFeats,"temp_join_id","LONG")
       with arcpy.da.UpdateCursor(inFeats,"temp_join_id") as cursor:
           for row in cursor:
               row[0] = i
               cursor.updateRow(row)
               i+=1
   
   #create service area line layer
   service_area_lyr = arcpy.na.MakeServiceAreaLayer(network,os.path.join(scratchGDB,"service_area_temp"),"Length","TRAVEL_FROM",sepDist,polygon_type="NO_POLYS",line_type="TRUE_LINES",overlap="OVERLAP")
   service_area_lyr = service_area_lyr.getOutput(0)
   subLayerNames = arcpy.na.GetNAClassNames(service_area_lyr)
   facilitiesLayerName = subLayerNames["Facilities"]
   serviceLayerName = subLayerNames["SALines"]
   
   # generate centerpoints of features (1 per)
   facil1 = arcpy.FeatureToPoint_management(in_features=inFeats, out_feature_class= scratchGDB + os.sep + 'facil1', point_location="INSIDE")
   
   # generate 'facilities' (using junction points - this is alternate/less precise option than intersections option below)
   #facil2 = arcpy.SpatialJoin_analysis(str(network) + "_Junctions", inFeats, scratchGDB + os.sep + 'facil2', "JOIN_ONE_TO_ONE", "KEEP_COMMON", "#", "INTERSECT","", "")
   #facil = arcpy.Merge_management([facil1, facil2], scratchGDB + os.sep + 'facil', field_mappings="""temp_join_id "temp_join_id" true true false 4 Long 0 0 ,First,#,facil1,temp_join_id,-1,-1,facil2,temp_join_id,-1,-1""")
   
   # generate facilities using intersections of network + feature edges
   netlines = str(network).replace(os.path.basename(network),"NHDFlowline_Network") # NHDFlowline_Network is a is a fixed name, the lines that make up the network dataset. Stored in same Feature Dataset as ND
   printMsg("Generating facilities at intersections with network...")
   facil2 = arcpy.PolygonToLine_management(in_features=inFeats, out_feature_class= scratchGDB + os.sep + 'facil2')
   facil3 = arcpy.Intersect_analysis([netlines,facil2], scratchGDB + os.sep + 'facil3', output_type = "POINT")
   facil4 = arcpy.MultipartToSinglepart_management(facil3, scratchGDB + os.sep + 'facil4')
   facil5 = arcpy.Merge_management([facil1, facil4], scratchGDB + os.sep + 'facil5')
   # re-attach temp_join_id
   arcpy.DeleteField_management(facil5, "temp_join_id")
   facil = arcpy.SpatialJoin_analysis(facil5, inFeats, scratchGDB + os.sep + 'facil', join_operation="JOIN_ONE_TO_ONE", join_type="KEEP_ALL", match_option="INTERSECTS")

   # add locations and solve
   printMsg("Solving service areas...")
   arcpy.na.AddLocations(service_area_lyr, facilitiesLayerName, facil, "", "5000 Meters", search_criteria = [[str(netName), 'SHAPE']]) # large search tolerance to make sure all points get on network (large rivers with artificial paths)
   arcpy.na.Solve(service_area_lyr)
   lines = arcpy.mapping.ListLayers(service_area_lyr,serviceLayerName)[0]
   flowline_clip = arcpy.CopyFeatures_management(lines,os.path.join(scratchGDB,"service_area"))
   
   #buffer clipped flowlines by 1 meter
   flowline_buff = arcpy.Buffer_analysis(flowline_clip,os.path.join(scratchGDB,"flowline_buff"),"1 Meter","FULL","ROUND",dissolve_option="ALL")
   
   # merge service areas with original polys that intersect service areas (so they join up for polygons with multiple facility points)
   arcpy.MakeFeatureLayer_management(inFeats, 'inFeats') 
   arcpy.SelectLayerByLocation_management('inFeats', 'intersect', flowline_buff)
   flowline_merge = arcpy.Union_analysis([flowline_buff, 'inFeats'], os.path.join(scratchGDB,"flowline_merge"))
   arcpy.SelectLayerByAttribute_management('inFeats','CLEAR_SELECTION')
   
   #dissolve flowline buffers (single parts)
   flowline_diss = arcpy.Dissolve_management(flowline_merge,os.path.join(scratchGDB,"flowline_diss"),multi_part="SINGLE_PART")
   
   if barriers != "#":
       #buffer barriers by 1.1 meters
       dam_buff = arcpy.Buffer_analysis(barriers,os.path.join(scratchGDB,"dam_buff"),"1.1 Meter","FULL","FLAT")
       #split flowline buffers at dam buffers by erasing area of dam
       flowline_erase = arcpy.Erase_analysis(flowline_diss,dam_buff,os.path.join(scratchGDB,"flowline_erase"))
       multipart_input = flowline_erase
       #multi-part to single part to create unique polygons after erase
       single_part = arcpy.MultipartToSinglepart_management(multipart_input,os.path.join(scratchGDB,"single_part"))
   else:
       single_part = flowline_diss
   
   #create unique group id
   arcpy.AddField_management(single_part,fldGrpID,"LONG")
   num = 1
   with arcpy.da.UpdateCursor(single_part,fldGrpID) as cursor:
       for row in cursor:
           row[0] = num
           cursor.updateRow(row)
           num+=1
   
   #join group id of buffered flowlines to closest points
   s_join = arcpy.SpatialJoin_analysis(target_features=facil, join_features=single_part, out_feature_class=os.path.join(scratchGDB,"s_join"), join_operation="JOIN_ONE_TO_ONE", join_type="KEEP_ALL", match_option="CLOSEST", search_radius="5000 Meters", distance_field_name="")
   
   #join field to original dataset
   join_field = [field.name for field in arcpy.ListFields(s_join)]
   join_field = join_field[-1]
   # arcpy.JoinField_management(inFeats,"temp_join_id",s_join,"temp_join_id",join_field)
   JoinFields(inFeats, "temp_join_id",s_join,"temp_join_id",[fldGrpID])
   arcpy.DeleteField_management(inFeats, "temp_join_id")
   
   return inFeats

# internal spatial clustering function over network dataset
def SpatialClusterNetwork(software, species_pt, species_ln, species_py, flowlines, catchments, network, dams, sep_dist, snap_dist, output_lines):
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
      lns = arcpy.FeatureVerticesToPoints_management(species_ln,"lns", "ALL")
      species_lyrs.append(lns)

   if species_py:
      pys = arcpy.FeatureVerticesToPoints_management(species_py,"polys", "ALL")
      species_lyrs.append(pys)

   # merge the point layers together
   species_pt = arcpy.Merge_management(species_lyrs,"species_pt")

   #calculate separation distance to be used in tools. use half of original minus
   #1 to account for 1 meter buffer and overlapping buffers
   sep_dist = int(sep_dist)
   sep_dist = (sep_dist/2)-2

   #create temporary unique id for use in join field later
   i=1
   fieldnames = [field.name for field in arcpy.ListFields(species_pt)]
   if 'temp_join_id' not in fieldnames:
      arcpy.AddField_management(species_pt,"temp_join_id","LONG")
      with arcpy.da.UpdateCursor(species_pt,"temp_join_id") as cursor:
          for row in cursor:
              row[0] = i
              cursor.updateRow(row)
              i+=1

   #delete identical points with tolerance to increase speed
   arcpy.DeleteIdentical_management(species_pt,[fldFeatID.Name, "Shape"],"35 Meters")

   arcpy.AddMessage("Creating service area line layer")
   #create service area line layer
   service_area_lyr = arcpy.na.MakeServiceAreaLayer(network,"service_area_lyr","Length","TRAVEL_FROM",sep_dist,polygon_type="NO_POLYS",line_type="TRUE_LINES",overlap="OVERLAP")
   service_area_lyr = service_area_lyr.getOutput(0)
   subLayerNames = arcpy.na.GetNAClassNames(service_area_lyr)
   facilitiesLayerName = subLayerNames["Facilities"]
   serviceLayerName = subLayerNames["SALines"]
   arcpy.na.AddLocations(service_area_lyr, facilitiesLayerName, species_pt, "", snap_dist)
   arcpy.na.Solve(service_area_lyr)
   if software.lower() == "arcmap":
      lines = arcpy.mapping.ListLayers(service_area_lyr,serviceLayerName)[0]
   if software.lower() == "arcgis pro":
      lines = service_area_lyr.listLayers(serviceLayerName)[0]
   flowline_clip = arcpy.CopyFeatures_management(lines,"service_area")

   arcpy.AddMessage("Buffering service area flowlines")
   #buffer clipped service area flowlines by 1 meter
   flowline_buff = arcpy.Buffer_analysis(flowline_clip,"flowline_buff","1 Meter","FULL","ROUND")

   arcpy.AddMessage("Dissolving service area polygons")
   #dissolve flowline buffers
   flowline_diss = arcpy.Dissolve_management(flowline_buff,"flowline_diss",multi_part="SINGLE_PART")

   #separate buffered flowlines at dams
   if dams:
      #buffer dams by 1.1 meters
      dam_buff = arcpy.Buffer_analysis(dams,"dam_buff","1.1 Meter","FULL","FLAT")
      #split flowline buffers at dam buffers by erasing area of dam
      flowline_erase = arcpy.Erase_analysis(flowline_diss,dam_buff,"flowline_erase")
      multipart_input = flowline_erase
   else:
      multipart_input = flowline_diss

   #multi-part to single part to create unique polygons
   single_part = arcpy.MultipartToSinglepart_management(multipart_input,"single_part")


   #create unique group id
   group_id = fldGrpID.Name # unique to this toolbox
   arcpy.AddField_management(single_part,group_id,"LONG")
   num = 1
   with arcpy.da.UpdateCursor(single_part,group_id) as cursor:
      for row in cursor:
          row[0] = num
          cursor.updateRow(row)
          num+=1

   #join group id of buffered flowlines to closest points
   s_join = arcpy.SpatialJoin_analysis(target_features=species_pt, join_features=single_part, out_feature_class="s_join", join_operation="JOIN_ONE_TO_ONE", join_type="KEEP_ALL", match_option="CLOSEST", search_radius=snap_dist, distance_field_name="")
   #join field to original dataset
   join_field = [field.name for field in arcpy.ListFields(s_join)]
   join_field = join_field[-1]
   arcpy.JoinField_management(species_pt,"temp_join_id",s_join,"temp_join_id",join_field)

   #delete null groups to get rid of observations that were beyond snap_dist
   with arcpy.da.UpdateCursor(species_pt,join_field) as cursor:
      for row in cursor:
          if row[0] is None:
              cursor.deleteRow()

   arcpy.AddMessage("Joining COMID")
   #join species_pt layer with catchments to assign COMID
   sp_join = arcpy.SpatialJoin_analysis(species_pt,catchments,"sp_join","JOIN_ONE_TO_ONE","KEEP_COMMON","","INTERSECT")
   sp_join = arcpy.DeleteIdentical_management(sp_join,[group_id,"FEATUREID"])
   if len(arcpy.ListFields(sp_join,"COMID")) == 0:
      arcpy.AddField_management(sp_join,"COMID","LONG")
      with arcpy.da.UpdateCursor(sp_join,["FEATUREID","COMID"]) as cursor:
          for row in cursor:
              row[1] = str(row[0])
              cursor.updateRow(row)

   #obtain list of duplicate COMID because these are reaches assigned to multiple groups
   freq = arcpy.Frequency_analysis(sp_join,"freq","COMID")
   dup_comid = []
   with arcpy.da.SearchCursor(freq,["FREQUENCY","COMID"]) as cursor:
      for row in cursor:
          if row[0] > 1:
              dup_comid.append(row[1])

   arcpy.AddMessage("Resolving same reaches assigned to different groups")
   #get all groups within duplicate reaches and assign them to a single group
   sp_join_lyr = arcpy.MakeFeatureLayer_management(sp_join,"sp_join_lyr")
   if dup_comid:
      for dup in dup_comid:
          arcpy.SelectLayerByAttribute_management(sp_join_lyr,"NEW_SELECTION","COMID = {0}".format(dup))
          combine_groups = []
          with arcpy.da.SearchCursor(sp_join_lyr,[group_id]) as cursor:
              for row in cursor:
                  combine_groups.append(row[0])
          arcpy.SelectLayerByAttribute_management(sp_join_lyr,"NEW_SELECTION",fldGrpID.Name + " IN ({0})".format(','.join(str(x) for x in combine_groups)))
          with arcpy.da.UpdateCursor(sp_join_lyr,[group_id]) as cursor:
              for row in cursor:
                  row[0] = num
                  cursor.updateRow(row)
          num += 1

   #clear selection on layer
   arcpy.SelectLayerByAttribute_management(sp_join_lyr,"CLEAR_SELECTION")

   #get list of COMID values for export of flowlines
   with arcpy.da.SearchCursor(sp_join_lyr,"COMID") as cursor:
      comid = sorted({row[0] for row in cursor})
   comid = list(set(comid))

   #join attributes to flowlines
   expression = 'COMID IN ({0})'.format(','.join(str(x) for x in comid))
   flowlines_lyr = arcpy.MakeFeatureLayer_management(flowlines,"flowlines_lyr",expression)
   arcpy.AddJoin_management(flowlines_lyr,"COMID",sp_join,"COMID")

   arcpy.env.qualifiedFieldNames = False
   
   # export presence flowlines
   flowlines_lyr = arcpy.CopyFeatures_management(flowlines_lyr,"flowlines_lyr")
   # reduce fields
   myfields = ['COMID','FEATUREID','SOURCEFC'] + initDissList
   # create an empty field mapping object
   mapS = arcpy.FieldMappings()
   # for each field, create an individual field map, and add it to the field mapping object
   for field in myfields :
      arcpy.AddMessage("field: " + field)
      try:
         map = arcpy.FieldMap()
         map.addInputField(flowlines_lyr, field)
         mapS.addFieldMap(map)
      except:
         next
   arcpy.FeatureClassToFeatureClass_conversion(flowlines_lyr, os.path.dirname(output_lines), os.path.basename(output_lines), "#", mapS)
   
   # append group IDs to original datasets
   if species_py:
      species_pt = arcpy.DeleteIdentical_management(species_pt, [fldFeatID.Name, group_id])
      JoinFields(species_py, fldFeatID.Name, species_pt, fldFeatID.Name, [fldGrpID.Name])
   
   #delete temporary fields and datasets
   # arcpy.Delete_management("in_memory")
   return species_py


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
def MarkSpatialDuplicates(inPolys, fldDateCalc = 'sdm_date', fldSFRA = 'tempSFRACalc', fldUse = 'sdm_use', fldUseWhy = 'sdm_use_why', fldRaScore = 'sdm_ra'):
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
         raList = unique_values('lyrPolys', fldRaScore)
         maxRa = max(raList)
         
         # Unselect any records where the RA is less than the maximum
         where_clause2 = "%s < %s" % (fldRaScore, maxRa)
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
fldSrcFID = Field('src_fid','LONG','') # original source table FID (auto-populated)
fldSFID = Field('src_featid', 'LONG', '') # original feature's SFID or similar (Source feature ID in Biotics)
fldEOID = Field('src_grpid', 'TEXT', 50) # original group ID (EO ID in biotics)
fldUse = Field('sdm_use', 'SHORT', '') # Binary: Eligible for use in model training (1) or not (0)
fldUseWhy = Field('sdm_use_why', 'TEXT', 50) # Comments on eligibility for use
fldDateCalc = Field('sdm_date', 'TEXT', 10) # Date in standardized yyyy-mm-dd format
fldDateFlag = Field('sdm_date_flag', 'SHORT', '') # Flag uncertain year. 0 = certain; 1 = uncertain
fldRA = Field('sdm_ra', 'SHORT', '') # Source feature representation accuracy
fldSFRACalc = Field('tempSFRACalc', 'TEXT', 20) # for storing original RA column values for editing
fldRAFlag = Field('sdm_ra_flag', 'SHORT', '') # Flag for editing. 0 = okay; 1 = needs edits; 2 = edits done
fldFeatID = Field('sdm_featid', 'LONG', '') # new unique id by polygon
fldGrpID = Field('sdm_grpid', 'TEXT', 50) # new unique id by group
# fldComments = Field('revComments', 'TEXT', 250) # Field for review/editing comments; dropping in favor of UseWhy

initFields = [fldSpCode, fldSrcTab, fldSrcFID, fldSFID, fldEOID, fldUse, fldUseWhy, fldDateCalc, fldDateFlag, fldRA, fldSFRACalc, fldRAFlag, fldFeatID, fldGrpID] 
initDissList = [f.Name for f in initFields]

# not using these
# fldIsDup, fldRev, fldComments
# Additional fields for automation
#fldRaScore = Field('raScore', 'SHORT', '') # Quality score based on Representation Accuracy
#fldDateScore = Field('dateScore', 'SHORT', '') # Quality score based on date
#fldPQI = Field('pqiScore', 'SHORT', '') # Composite quality score ("Point Quality Index")
#fldGrpUse = Field('grpUse', 'LONG', '') # Identifies highest quality records in group (1) versus all other records (0)
# addFields = [fldRaScore, fldDateScore, fldPQI, fldGrpUse]

def fc2df(feature_class, field_list, skip_nulls = True):
   """
   Load data into a Pandas Data Frame for subsequent analysis.
   :param feature_class: Input ArcGIS Feature Class.
   :param field_list: Fields for input.
   :return: Pandas DataFrame object.
   """
   import pandas
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

## FUNCTIONS FOR TOOLBOX STARTS HERE
class Toolbox(object):
   def __init__(self):
      self.label = "SDM Training Data Prep"
      self.alias = "sdmPresencePreProc"
      
      # List of tool classes associated with this toolbox (defined classes below)
      self.tools = [AddInitFlds, MergeData, GrpOcc]
      
class AddInitFlds(object):
   def __init__(self):
      self.label = "1. Create feature occurrence dataset"
      self.description ="Creates a prepared feature occurrence dataset " + \
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
            displayName = "Group (EO ID) column",
            name = "fldEO",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      
      fldSF = arcpy.Parameter(
            displayName = "Feature (SF ID) column",
            name = "fldSF",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
       
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
      srcTab =  srcTab.replace('.shp','')
      srcTab = make_gdb_name(srcTab)
      outPolys = outGDB + os.sep + srcTab + '_' + spCode
      
      params[7].value = outPolys
      
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
      
      # table fid (object/fid)
      a = arcpy.Describe(outPolys).Fields
      for a1 in a:
         if a1.Type == 'OID':
            fldID = str(a1.Name)
            break
      expression = "!%s!" % (fldID)
      arcpy.CalculateField_management (outPolys, fldSrcFID.Name, expression, 'PYTHON')
      printMsg('Unique ID field populated.')
      
      # use
      arcpy.CalculateField_management(outPolys, fldUse.Name, '1', "PYTHON")
      
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
         arcpy.CalculateField_management (outPolys, fldSFRACalc.Name, expression, 'PYTHON')
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
      q = "%s NOT IN ('Very High','High','Medium','Low','Very Low')" % fldSFRACalc.Name
      arcpy.SelectLayerByAttribute_management('outPolys','NEW_SELECTION', q)
      arcpy.CalculateField_management ('outPolys', fldRAFlag.Name, 1, "PYTHON")
      if (int(arcpy.GetCount_management('outPolys')[0]) > 0):
         printMsg("Some RA values are not in the allowed value list and were marked with '%s' = 1. Make sure to edit '%s' column for these rows." % (fldRAFlag.Name, fldSFRACalc.Name))
      arcpy.SelectLayerByAttribute_management('outPolys', 'CLEAR_SELECTION')
      
      return outPolys
   
# end AddInitFlds


# begin MergeData
class MergeData(object):
   def __init__(self):
      self.label = "2. Merge feature occurrence datasets"
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
            parameterType = "Derived",
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
      
      #if (params[0].value and not params[1].altered) or (params[0].value and not params[0].hasBeenValidated):
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
      outPolysNm = str(arcpy.Describe(inGDB).name.replace('.gdb','')) + '_merged_' + today
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
         sr = arcpy.Describe(spatialRef).spatialReference
         
      # Make a new polygon feature class for output
      outPolys_temp = outPolysNm + '_temp'
      outPolys_temp2 = outPolysNm + '_notDissolved'
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
      # these are for automatic scoring and not being used currently.
      #for f in addFields:
      #   arcpy.AddField_management (outPolys_temp, f.Name, f.Type, '', '', f.Length)
      
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
         arcpy.Select_analysis(u_all, inList_u2[i], where_clause = fld + " <> -1 and " + fldUse.Name + " <> 0")
         arcpy.Append_management (inList_u2[i], outPolys_temp, 'NO_TEST')
         # dissolve eliminates polys that are EXACT duplicates, since initDissList includes all fields
         arcpy.Dissolve_management(outPolys_temp, outPolys_temp2, initDissList2, "", "SINGLE_PART")
      
      # get rid of all temp files
      garbagePickup(inList_u + inList_u2 + [outPolys_temp] + ["union_all"])
      printMsg('Data merge complete.')
      
      # identify spatial duplicates (internal function)
      MarkSpatialDuplicates(outPolys_temp2, fldDateCalc = fldDateCalc.Name, fldSFRA = fldSFRACalc.Name, fldUse = fldUse.Name, fldUseWhy = fldUseWhy.Name, fldRaScore = fldRA.Name)
      
      # final dissolve
      try:
         arcpy.Dissolve_management(outPolys_temp2, outPolys, initDissList, "", "SINGLE_PART")
         arcpy.DeleteField_management(outPolys, fldSFRACalc.Name)
      except:
         printMsg('Final dissolve failed. Need to dissolve on all attributes (except fid/shape/area) to finalize dataset: ' + str(outPolys_temp2))
         return
      
      garbagePickup([outPolys_temp2])
      return outPolys
      
      
class GrpOcc(object):
   def __init__(self):
      self.label = "3. Finalize/Group occurrences"
      self.description ="Groups occurrences in a merged feature occurrence dataset," + \
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
            name = "sepDist",
            datatype = "GPString",
            parameterType = "Optional",
            direction = "Input")
            
      grpFld = arcpy.Parameter(
            displayName="Field for group IDs",
            name = "grpFld",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
            
      network = arcpy.Parameter(
            displayName="Network dataset (requires Network Analyst extension)",
            name = "network",
            datatype = "DENetworkDataset",
            parameterType = "Optional",
            direction = "Input")
            
      barriers = arcpy.Parameter(
            displayName="Feature barriers",
            name = "barriers",
            datatype = "DEFeatureClass",
            parameterType = "Optional",
            direction = "Input")
            
      outPolys = arcpy.Parameter(
            displayName="Output Features",
            name="outPolys",
            datatype="DEFeatureClass",
            parameterType="Derived",
            direction="Output")
      
      tolerance = arcpy.Parameter(
            displayName = "Maximum distance tolerance",
            name = "tolerance",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      tolerance.value = "100"
            
      grpFld.parameterDependencies = [inPolys.name]
      params = [inPolys,sepDist,grpFld,network,barriers,outPolys,tolerance]
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
      arcpy.Select_analysis(inPolys,inPolys2,fldUse.Name + ' = 1')
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
            SpatialCluster(inFeats = inPolys2, sepDist = sepDist, fldGrpID = grpFld)
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
            inPolys2 = SpatialClusterNetwork(software = "ArcMap", species_pt = None, species_ln = None, species_py = inPolys2, 
               flowlines = flowlines, catchments = catchments, network = network, dams = barriers, 
               sep_dist = sepDist, snap_dist = tolerance, output_lines = outLines)
            # returns inPolys2 with group ID column populated
      else:
         # just update column from src_grpid
         arcpy.CalculateField_management(inPolys2, fldGrpID.Name, '!' + fldEOID.Name + '!', 'PYTHON')
      
      uv = unique_values(inPolys2, fldGrpID.Name)
      if '' in uv or ' ' in uv:
         printWrng('Some grouping ID values in ' + fldGrpID.Name + ' are empty. Make sure to populate these prior to modeling.')
      arcpy.CopyFeatures_management(inPolys2, outPolys)
      
      return outPolys
      
# GetLines (for aquatics)
      
class GetLines(object):
   def __init__(self):
      self.label = "4. Select Lines by polygon occurrences"
      self.description ="Takes a prepared polygon feature occurrence dataset " + \
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
            multiValue = True)
            
      outLines = arcpy.Parameter(
            displayName = "Output feature class",
            name = "outLines",
            datatype = "DEFeatureClass",
            parameterType = "Derived",
            direction = "Output")
            
      inPolysID = arcpy.Parameter(
            displayName = "Unique polygon ID field",
            name = "inPolysID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
            
      inLinesID = arcpy.Parameter(
            displayName = "Unique lines ID field",
            name = "inLinesID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
            
      tolerance = arcpy.Parameter(
            displayName = "Maximum distance tolerance",
            name = "tolerance",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
            
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
      import numpy as np
      import pandas
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
      df = DataFrame(columns = [inPolysID, inLinesID, 'type'])
      if int(str(arcpy.GetCount_management(inter))) > 0:
         df_inter = fc2df(inter, [inPolysID, inLinesID])
         df_inter["type"] = '1_intersection'
         df = df.append(df_inter)
      
      # get all areawb intersections and associate a line
      printMsg('Finding nearest line in intersecting area features...')
      dl = arcpy.MakeFeatureLayer_management(lyr_all, 'lyr_all') # for first intersect
      dl2 = arcpy.MakeFeatureLayer_management(lyr_all, 'lyr_all') # for tracking those polygons that intersect areas
      alines = arcpy.MakeFeatureLayer_management(inLines, 'arealines')
      area_wb = []
      for a in inAreas:
         a1 = arcpy.MakeFeatureLayer_management(a)
         arcpy.SelectLayerByLocation_management(a1, "INTERSECT", dl) # get intersecting areas
         if int(str(arcpy.GetCount_management(a1))) > 0:
            arcpy.SelectLayerByLocation_management(alines, "COMPLETELY_WITHIN", a1, selection_type = "ADD_TO_SELECTION") # select lines within those areas
            arcpy.SelectLayerByLocation_management(dl2, "INTERSECT", a1, selection_type = "ADD_TO_SELECTION") # select polys intersecting those areas
            area_wb.extend(unique_values(a1, inLinesID))
      
      # get lines based on areawb selection, if any
      if len(area_wb) > 0:
         #str1 = '\',\''.join(area_wb)
         #a1 = arcpy.MakeFeatureLayer_management(inLines, 'arealines') #, '"WBArea_Permanent_Identifier" in (\'' + str1 + '\')')
      
         # a1 is now lines intersecting the intersecting wbareas
         # take subset that do not intersect an area boundary
         # select all first (only necessary for the boundary touches method. Not using since it requires fixed id in 'a1 = ' step above
         # arcpy.SelectLayerByAttribute_management(a1, "NEW_SELECTION")
         #for a in inAreas:
            #arcpy.SelectLayerByLocation_management(a1, "COMPLETELY_WITHIN", a, "#", "ADD_TO_SELECTION")
            # arcpy.SelectLayerByLocation_management(a1, "BOUNDARY_TOUCHES", a, "#", "REMOVE_FROM_SELECTION")
         
         # spatial join closest (no limit on distance, since these polys already intersect an area feature)
         near_area_wb = arcpy.SpatialJoin_analysis(dl2, alines, scratchGDB + os.sep + 'sj_wb', join_operation="JOIN_ONE_TO_ONE", join_type="KEEP_COMMON", match_option="CLOSEST")
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
         near = arcpy.SpatialJoin_analysis(dl, inLines, scratchGDB + os.sep + 'sj', join_operation="JOIN_ONE_TO_MANY", join_type="KEEP_ALL", match_option="WITHIN_A_DISTANCE", search_radius = tolerance)
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
      
      fieldList = [['outl.' + inLinesID, inLinesID],['jointab.'  + inPolysID, inPolysID], ['outl.Shape', 'Shape']]
      where = "outl." + inLinesID  + " = jointab." + inLinesID
      
      # join poly ids to selected lines
      arcpy.MakeQueryTable_management([linesel,'jointab'], "lines0", in_field = fieldList, where_clause = where)
      arcpy.CopyFeatures_management("lines0", "lines0_feat")
      
      # join original poly info
      arcpy.MakeQueryTable_management(['lines0_feat','inPolysTab'], "lines1", where_clause = 'lines0_feat.' + inPolysID + ' = inPolysTab.' + inPolysID)
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
                  grps1 = grps0 + 1 # new group number
                  grps0 = grps1 # for next time
                  arcpy.SelectLayerByAttribute_management(layer, "NEW_SELECTION", '"' + inLinesID + '" = ' + "'" + str(row[1]) + "'") # select lines by id
                  uv = ','.join([str(s) for s in unique_values(layer, fldGrpID.Name)])
                  arcpy.SelectLayerByAttribute_management(layer, "NEW_SELECTION", '"' + fldGrpID.Name + '" IN (' + uv + ')') # select lines by group
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
      self.description ="Takes a prepared polygon feature occurrence dataset " + \
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
            displayName = "Output feature class",
            name = "outLines",
            datatype = "DEFeatureClass",
            parameterType = "Derived",
            direction = "Output")
            
      tolerance = arcpy.Parameter(
            displayName = "Maximum distance tolerance",
            name = "tolerance",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      
      inLinesID = arcpy.Parameter(
            displayName = "Unique lines ID field",
            name = "inLinesID",
            datatype = "GPString",
            parameterType = "Required",
            direction = "Input")
      
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
      p1 = arcpy.Dissolve_management(lyr_poly, "p1",  dissolve_field="", statistics_fields="", multi_part="SINGLE_PART", unsplit_lines="DISSOLVE_LINES")
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
      arcpy.Near_analysis(line_pts, p1_line, search_radius="", location="NO_LOCATION", angle="NO_ANGLE", method="PLANAR")
      line_pts_summ = arcpy.Statistics_analysis(line_pts, out_table='line_pts_summ', statistics_fields="NEAR_DIST STD;NEAR_DIST MEAN;NEAR_DIST RANGE", case_field= inLinesID + ";slength")
      
      # calculate score
      arcpy.AddField_management(line_pts_summ, 'score', 'FLOAT')
      arcpy.CalculateField_management(line_pts_summ, 'score',  expression= "(" + tol_dist + " - (!MEAN_NEAR_DIST! * (!STD_NEAR_DIST! / !slength!))) / " + tol_dist, expression_type="PYTHON", code_block="")
      # arcpy.CalculateField_management(line_pts_summ, 'score',  expression= "(" + tol_dist + " - (!MEAN_NEAR_DIST! * (!RANGE_NEAR_DIST! / !slength!))) / " + tol_dist, expression_type="PYTHON", code_block="")
      
      # output lines
      outLines = arcpy.CopyFeatures_management(lyr_line, out_feature_class= outLines)
      arcpy.JoinField_management(outLines, inLinesID, line_pts_summ, inLinesID, fields="slength;score")
      
      # calculate a threshold (minimum of the [maximum scores by original feature within tolerance distance])
      inpoly_sj = arcpy.SpatialJoin_analysis(inPolys, outLines, "inpoly_sj", "JOIN_ONE_TO_MANY","KEEP_COMMON", match_option="WITHIN_A_DISTANCE", search_radius= tolerance)
      inpoly_max = arcpy.Statistics_analysis(inpoly_sj, "inpoly_max", statistics_fields="score MAX", case_field= fldFeatID.Name)
      thresh = min(unique_values(inpoly_max, "MAX_score"))
      printMsg("Using a threshold of score >= " + str(thresh) + "...")
      
      # new layer to select closest by original polygons
      outlines1 = arcpy.MakeFeatureLayer_management(outLines)
      p1 = arcpy.MakeFeatureLayer_management(p1)
      arcpy.SelectLayerByLocation_management(p1, "WITHIN_A_DISTANCE", lyr_line, tolerance, invert_spatial_relationship = "INVERT")
      arcpy.SelectLayerByLocation_management(lyr_poly, "INTERSECT", p1, selection_type = "NEW_SELECTION")
      # nearest line by these polys
      ct = arcpy.GetCount_management(lyr_poly)[0]
      if int(ct) > 0:
         printMsg('Appending nearest lines for ' + ct + ' polygon(s) not within tolerance distance (score will == 1)...')
         arcpy.SelectLayerByAttribute_management(lyr_line, selection_type = "CLEAR_SELECTION")
         arcpy.Near_analysis(lyr_poly, lyr_line, search_radius = "5000 meters")
         getids = ','.join(str(i) for i in unique_values(lyr_poly, "NEAR_FID"))
         arcpy.SelectLayerByAttribute_management(lyr_line, "NEW_SELECTION", '"' + linesOID + '" in (' + getids + ')')
         outlines2 = arcpy.CopyFeatures_management(lyr_line, out_feature_class= "outlines2")
         arcpy.AddField_management(outlines2, 'score', 'FLOAT')
         arcpy.CalculateField_management(outlines2, 'score',  1, expression_type="PYTHON")
         arcpy.Append_management(outlines2, outLines, "NO_TEST")
      
      # use threshold to assign sdm_use value to flowlines
      arcpy.AddField_management(outLines, fldUse.Name, 'INTEGER')
      arcpy.CalculateField_management(outLines, fldUse.Name, expression="fn(!score!," + str(thresh) + ")", expression_type="PYTHON", 
      code_block="def fn(s, t):\n   if s >= t:\n      return 1\n   else:\n      return 0\n")
      
      return outLines