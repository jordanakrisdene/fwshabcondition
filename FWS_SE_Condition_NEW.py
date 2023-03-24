import arcpy, os, re
from arcpy.sa import *

# Check out any necessary licenses.
arcpy.CheckOutExtension("spatial")

scratchWorkspace = r"FWS_ScratchWorkspace.gdb"

# set up environments
arcpy.env.extent = "1272796.01889252 837937.189808734 1293290.19762114 851783.705021468" # temporary
arcpy.env.workspace = r"S:\Projects\USFWS\SE_FWS_Habitat_2022\FWS_HabConScriptTesting"
arcpy.env.scratchWorkspace = os.path.join(arcpy.env.workspace,scratchWorkspace)
# check if the scratch geodatabase exists
if arcpy.Exists(arcpy.env.scratchWorkspace):
    # if it exists, delete it
    arcpy.Delete_management(arcpy.env.scratchWorkspace)
    print("Geodatabase deleted.")
else:
    # if it doesn't exist, print a message
    print("Geodatabase does not exist.")

arcpy.management.CreateFileGDB(arcpy.env.workspace, scratchWorkspace)

HabitatCondition_gdb = r"FWS_HabConScriptTesting.gdb"
arcpy.env.overwriteOutput =  True

# Input Variables
hexgrid = r"S:\Projects\USFWS\SE_FWS_Habitat_2022\SE_FWS_HabitatCondition\SE_FWS_HabitatCondition.gdb\GenerateTessellation100acres"
combined_EVT_tif = r"S:\Projects\_Workspaces\Jordana_Anderson\SE_USFWS\FWS_SE_Condition\FWS_SE_Condition_testing\FWS_SE_Condition_testing.gdb\combined_EVT_Clip"
hexclip = r"S:\Projects\USFWS\SE_FWS_Habitat_2022\FWS_HabConScriptTesting\FWS_HabConScriptTesting.gdb\hexclip"                             
dataLCM = r"S:\Data\NatureServe\Landscape_Condition\Americas_N_LCM_Cat100.tif"
dataRuderal = r"S:\Projects\USFWS\SE_FWS_Habitat_2022\SE_FWS_HabitatCondition\Ruderal_5cell_scaled.tif"
dataFireDep = r"S:\Data\External\LANDFIRE_Fire_Departure\LF2020_VDep_220_CONUS\LF2020_VDep_220_CONUS\Tif\LC20_VDep_220.tif"

templateInvasiveSource = r"S:\Projects\USFWS\SE_FWS_Habitat_2022\FWS_HabConScriptTesting\fwshabcondition\template_InvasiveSource.lyrx"
templateLCM = r"S:\Projects\USFWS\SE_FWS_Habitat_2022\FWS_HabConScriptTesting\fwshabcondition\template_LCM.lyrx"

outExtractByMask = ExtractByMask(combined_EVT_tif, hexclip)  # THIS WILL LIKELY HAVE TO BE MODIFED FOR THE FULL SCRIPT!!!!
outExtractByMask1 = ExtractByAttributes(outExtractByMask, '"Value_1" <> 0') 
outExtractByMask1.save("EVTclip.tif")

value_list = [] 
with arcpy.da.SearchCursor("EVTclip.tif", ["Value","NatureServ"]) as cursor:
    for row in cursor:
        value_list.append(row)

col_idx = 1

# for altering a text column later
#column = [row[1] for row in value_list] # use a list comprehension to extract the column of interest
#max_length = max(len(element) for element in column) + 10 # find the maximum length of the elements in the column
        
print("Creating condition datasets for " + str(len(value_list)) + " ecological systems.")
print("===============================================================================")

for index in value_list:
    EVTvalue = index[0]
    EVTname = index[1]
    # create a clean version of the system name filenames
    pattern = re.compile('[^a-zA-Z0-9\s]+')
    EVTclean = re.sub(pattern, '', EVTname)
    pattern = re.compile('\s+')
    EVTclean = re.sub(pattern, '', EVTclean)
    
    print("working on " + EVTname + " (EVT " + str(EVTvalue) + ")")
        
    # Process: Extract by Attributes (Extract by Attributes) (sa)
    print("- working on extracting the EVT data")
    nameEVT = "tmp_Extract_" + str(EVTvalue) + ".tif"
    w_clause = '"VALUE" = ' + "%s" %EVTvalue
    tmp_Extract_Value_tif = ExtractByAttributes(in_raster="EVTclip.tif", where_clause=w_clause)
    tmp_Extract_Value_tif.save(os.path.join(arcpy.env.workspace, nameEVT))

    # Select out the hexagons that overlap the EVT cells
    print("- intersecting the EVT layer with the hex grid")
    tmp_Value_raster2pt = fr"tmp_{EVTvalue}_raster2pt"
    arcpy.conversion.RasterToPoint(in_raster=tmp_Extract_Value_tif, out_point_features=tmp_Value_raster2pt, raster_field="VALUE")    
    hexgridselection = arcpy.management.SelectLayerByLocation(in_layer=[hexgrid], overlap_type="INTERSECT", select_features=tmp_Value_raster2pt, search_distance="", selection_type="NEW_SELECTION", invert_spatial_relationship="NOT_INVERT")
    hexgridselection = arcpy.conversion.FeatureClassToFeatureClass(in_features=hexgridselection, out_path=os.path.join(arcpy.env.workspace,HabitatCondition_gdb), out_name=f"hex100ac_{EVTclean}", where_clause="")

    arcpy.management.CalculateField(in_table=hexgridselection, field="EVTcode", expression=EVTvalue, field_type="LONG")
    arcpy.management.CalculateField(in_table=hexgridselection, field="EVTname", expression="'" + EVTname + "'", field_type="TEXT")
    #arcpy.management.AlterField(in_table=hexgridselection, field="EVTname", new_field_alias="EVT name", field_type="TEXT", field_length=max_length)

    # Work on the LCM
    print("- calculating and summarizing the LCM values")
    tmp_Value_LCM_tif = fr"tmp_{EVTvalue}_LCM.tif"
    tmp_Value_LCM_tif = arcpy.sa.ExtractByMask(in_raster=dataLCM, in_mask_data=nameEVT)
    ZonalSt_Value_LCM = fr"ZonalSt_{EVTvalue}_LCM"
    arcpy.sa.ZonalStatisticsAsTable(in_zone_data=hexgridselection, zone_field="GRID_ID", in_value_raster=tmp_Value_LCM_tif,
                                    out_table=ZonalSt_Value_LCM, ignore_nodata="DATA", statistics_type="MEAN")
    arcpy.management.JoinField(in_data=hexgridselection, in_field="GRID_ID", join_table=ZonalSt_Value_LCM, join_field="GRID_ID", fields=["MEAN"])[0]
    arcpy.management.CalculateField(in_table=hexgridselection, field="scoreLCM", expression="round(!MEAN!,1)", field_type="DOUBLE")
    arcpy.management.DeleteField(hexgridselection, "MEAN")
    arcpy.management.AlterField(hexgridselection, "scoreLCM", "scoreLCM", "LCM Score") 

    # Work on Invasive Risk score
    print("- calculating the invasive risk score")
    tmp_InvRisk_tif = fr"tmp_{EVTvalue}_Inv.tif"
    tmp_InvRisk_tif = arcpy.sa.ExtractByMask(in_raster=dataRuderal, in_mask_data=nameEVT)
    ZonalSt_Value_InvRisk = fr"ZonalSt_{EVTvalue}_InvRisk"
    arcpy.sa.ZonalStatisticsAsTable(in_zone_data=hexgridselection, zone_field="GRID_ID", in_value_raster=tmp_InvRisk_tif,
                                    out_table=ZonalSt_Value_InvRisk, ignore_nodata="DATA", statistics_type="MEAN")
    arcpy.management.JoinField(in_data=hexgridselection, in_field="GRID_ID", join_table=ZonalSt_Value_InvRisk, join_field="GRID_ID", fields=["MEAN"])[0]
    arcpy.management.CalculateField(in_table=hexgridselection, field="scoreInv", expression="round(!MEAN!,1)", field_type="DOUBLE")
    arcpy.management.DeleteField(hexgridselection, "MEAN")
    arcpy.management.AlterField(hexgridselection, "scoreInv", "scoreInv", "Invasive Score") 

    # calculating the mean condition/quality score
    arcpy.management.CalculateField(in_table=hexgridselection, field="scoreInvR", expression="Abs($feature.scoreInv-100)", expression_type="ARCADE", code_block="", field_type="DOUBLE", enforce_domains="NO_ENFORCE_DOMAINS")
    arcpy.management.CalculateField(in_table=hexgridselection, field="meanCond", expression="(!scoreLCM!+!scoreInvR!)/2", expression_type="PYTHON3", code_block="", field_type="DOUBLE", enforce_domains="NO_ENFORCE_DOMAINS")
    arcpy.management.AlterField(hexgridselection, "meanCond", "meanCond", "Mean Condition")
    
    # Work on fire departure score
    print("- calculating the fire departure score")
    tmp_FireDep_tif = fr"tmp_{EVTvalue}_Inv.tif"
    tmp_FireDep_tif = arcpy.sa.ExtractByMask(in_raster=dataFireDep, in_mask_data=nameEVT)
    ZonalSt_Value_FireDep = fr"ZonalSt_{EVTvalue}_InvRisk"
    arcpy.sa.ZonalStatisticsAsTable(in_zone_data=hexgridselection, zone_field="GRID_ID", in_value_raster=tmp_FireDep_tif,
                                    out_table=ZonalSt_Value_FireDep, ignore_nodata="DATA", statistics_type="MEAN")
    arcpy.management.JoinField(in_data=hexgridselection, in_field="GRID_ID", join_table=ZonalSt_Value_FireDep, join_field="GRID_ID", fields=["MEAN"])[0]
    arcpy.management.CalculateField(in_table=hexgridselection, field="scoreFire", expression="round(!MEAN!,1)", field_type="DOUBLE")
    arcpy.management.DeleteField(hexgridselection, "MEAN")
    arcpy.management.AlterField(hexgridselection, "scoreFire", "scoreFire", "Fire Departure Score") 

    # apply a layer file
##    print("- creating the layer files")
##    dst = str(hexgridselection) + ".lyrx"
##    #shutil.copyfile(templateLCM, dst)
##    arcpy.management.ApplySymbologyFromLayer(hexgridselection, templateLCM, "VALUE_FIELD scoreLCM scoreLCM", "DEFAULT")
##    arcpy.management.SaveToLayerFile(hexgridselection, dst, "RELATIVE")

    # clean up
    print("- Cleaning up the crumbs")
    arcpy.management.Delete(in_data=[tmp_Value_raster2pt])   

# higher level cleanup


#arcpy.management.Delete(scratchWorkspace)
