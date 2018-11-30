# Prepping species observations for SDM

Author: David Bucklin

Last updated: 2018-11-02

## To add the toolbox to ArcMap:

- copy folder `I:\DATA_MGT\Division\SDM\TrainingData\_ArcToolbox\sdm_obs_prep_arcToolbox` to your computer
- Open ArcMap, and open list of Toolboxes
- Right click ArcToolbox at the top, and click `Add Toolbox`.
- navigate to where you copied the folder, and add `toolbox-arc.pyt`.
- The name of the toolbox in your list is **SDM Training Data Prep**
- Right click `ArcToolbox -> Save Settings -> To Default` and the toolbox will remain in the Toolbox list from now on

---

## Steps to prepare SDM training data for each species: 

#### 1. Prepare observation features layers (for each source dataset)

- If source is:
  -  **Biotics**:
    - use EOs or procedural features
    - we will need at least the observation date field, the RA field, EO_ID, and SF_ID
  - for **all other sources**:
    - ***If not already polygons:*** buffer the observations to create a polygon feature layer
    - retain date column. If one doesn't exist, add it and fill out best as you can
- **For all layers**: exclude any features you know you are sure you want to exclude from SDM training data
  - not required at this stage, but it will save processing and review time in step 3
  - if in doubt, leave them in

#### 2. For each observation feature layer, create observation feature classes using tool *'Create Observation Feature Class'*

- for each observation features layer, Run 'Create Observation Feature Class'.
  - If the observation features layer doesn't have an RA column (e.g. DGIF data), use "#" for that parameter
- This tool outputs one feature class for each observation features layer, with the same name as the input. 
- Output all feature classes for one species into one geodatabase. It is best to use a new Geodatabase for each species.
- The output file will have a new set of fields appended to the end of the table

#### 3. Clean up each observation feature class

- Sort by the `sdm_ra_flag` column; features marked `1` need attention due to SFRA attributes:
  - `tempSFRACalc`: this is required for SDM and should not have empty (Null) values. Assign one of the coded values (`Very High`, `High`, `Medium`, `Low`, or `Very Low`) for every feature. These ranks are also used to select a preferred polygon to use in overlapping areas
- Sort by the `sdm_date_flag` column; features marked `1` need attention due to date attributes:
  - `sdm_date` : try to add or fix any dates which have `sdm_date_flag = 1`. Dates are not required, but will be used to rank overlapping polygons when RA is equal. Dates are also used to tag environmental conditions for temporal variables (e.g. land cover), so a best guess is highly recommended here
    - If you don't know the month and/or day, you can use double zeros for those parts of the date (e.g. `2015-07-00` or `2001-00-00`)
- ***Optional***: you can also update the `sdm_use` and `sdm_use_why` columns now to exclude features (by setting `sdm_use = 0`) from further processing: these will not be in the merged datasets created in step 4.

#### 4. Merge datasets into a SDM training dataset using tool *'Merge Observation Feature Classes'*

- **IMPORTANT**: Do this step even if you only have one observation feature class. 
  - It will finalize the dataset with a standard set of fields, and mark duplicated areas among polygons, if they exist
- If you want to include only a subset of the observation features classes in the geodatabase, you need to check the boxes next to them. With none checked, it will use all feature classes in the geodatabase
- The output feature class needs to be output to a geodatabase
- This tool will only carry over occurrences marked `sdm_use = 1`
- This step creates several intermediate files during processing. Avoid accessing the input/output geodatabase during execution

#### 5. Edit SDM training dataset as needed

The resulting file from step 4 will have spatial duplicates identified, in the `sdm_use` and `sdm_use_why` columns, preferring higher RA values and later dates of observations

- features marked `sdm_use = 1` are the highest ranked features and will not overlap any other `sdm_use = 1` feature.
- `sdm_use = 0` are spatial duplicates. These spatially overlapped with another feature with a higher rank (higher RA or later date)

- now edit the file as needed for SDM 
  - these will be primarily spatial edits
  - table edits should be limited to adding comments or changing `use` field to further exclude features
  - assign  `sdm_use = 0` to features you want to exclude from the training data, and put in reasoning in `sdm_use_why`

#### 6. Finalize dataset

- After finished with spatial edits, a group ID needs to be added. This can be done with the **3. Finalize/Group occurrences** tool. 
- This tool will only carry over occurrences marked `sdm_use = 1`
- It can group in different ways, depending on what parameters are specified:
  - If you don't put in a distance, groups will be copied over from `src_grpid` (e.g. the original EO_ID)
  - If you put in a distance, automatic grouping by that separation distance will be used
  - If you put in a distance and a network dataset, automatic grouping by separation distance along the network will be used (e.g. for aquatic species)
- The output dataset will have `sdm_featid` and `sdm_grpid` populated. It will print a warning if there are empty `sdm_grpid` values. This will likely only be the case if you copied over from `src_grpid`, and had empty values in that column.

#### 7. Tag lines based on polygons [optional for aquatics]

- Use the tool **4. Select Lines by polygon occurrences** to create a new lines feature class, with lines attributed with the related feature occurrence
- Use the output from the grouping tool as the input polygons
- Duplicate lines are removed
  - If the same line is related to occurrences in multiple groups, those groups are combined into one new group
- After running, use the `sdm_use` column to set reaches that should not be included in the model to `0`.

---





- Still to do:
  - converts polygons to point for networking grouping: better options for this?
  - implement barriers for terrestrial grouping?

