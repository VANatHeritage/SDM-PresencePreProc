# Prepping species observations for SDM

Author: David Bucklin

Last updated: 2008-05-15

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
    - we will need the observation date field, the RA field, EO_ID, and SF_ID
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

- Sort by the `NeedEdit` column; features marked `1` need attention due to either date or SFRA attributes:
  - `SFRACalc`: this is required for SDM and should not have empty (Null) values. Assign one of the coded values (`Very High`, `High`, `Medium`, `Low`, or `Very Low`) for every feature. These ranks are also used to select a preferred polygon to use in overlapping areas
  - `dateCalc` : try to add or fix any dates which have `dateFlag` = 1. Dates are not required, but will be used to rank overlapping polygons when RA is equal. Dates are also used to tag environmental conditions for temporal variables (e.g. land cover), so a best guess is highly recommended here
    - If you don't know the month and/or day, you can use double zeros for those parts of the date (e.g. `2015-07-00` or `2001-00-00`)

#### 4. Merge datasets into a SDM training dataset using tool *'Merge Observation Feature Classes'*

- **IMPORTANT**: Do this step even if you only have one observation feature class. 
  - It will finalize the dataset with a standard set of fields, and mark duplicated areas among polygons, if they exist
- If you want to include only a subset of the observation features classes in the geodatabase, you need to check the boxes next to them. With none checked, it will use all feature classes in the geodatabase
- The output feature class needs to be output to a geodatabase. Best to output it to the input geodatabase
- This step creates several intermediate files during processing. Avoid accessing the input/output geodatabase during execution

#### 5. Edit SDM training dataset as needed

The resulting file from step 4 will have spatial duplicates identified, in the `use` and `use_why` columns, preferring higher RA values and later dates of observations

- features marked `use = 1` are the highest ranked features and will not overlap any other `use = 1` feature.
- `use = 0` are spatial duplicates. These spatially overlapped with another feature with a higher rank (higher RA or later date)

- now edit the file as needed for SDM 
  - these will be primarily spatial edits
  - table edits should be limited to adding comments or changing `use` field to further exclude features
  - assign  `use = 0` to features you want to exclude from the training data, and put in reasoning in `use_why`

---

These steps could  be automated later:

- Tagging reaches from aquatic polygons
- Adding group ids
  - option 1: use EO_ID (only works if all source polygons had this assigned)
  - option 2: use automatic grouping by a separation distance
    - for aquatics, could implement a stream-distance separation distance grouping
    - for terrestrial, a simple distance buffer should suffice
    - how to implement barriers?

