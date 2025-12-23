---
name: google-data-commons
description: Retrieve statistical and entity data from Google Data Commons about places, demographics, economics, health, education, climate, and other societal topics. For example, population/unemployment/social vulnerability index, etc.
---

# Google-Data-Commons Skill

## Description

This skill retrieves statistical and entity data from **Google Data Commons** using the **official Python Client Library (V2 API)**.
It wraps the most common workflows:
* **Resolve IDs:** Map common names/FIPS codes to canonical Data Commons IDs (DCIDs).
* **Statistical Observations:** Fetch time series and point-in-time values.
* **Pandas Integration:** Return data directly as Pandas DataFrames.

## When to Use

* When need to get population/unemployment/etc. for a place (for example, a state, or a county, or a census tract, or a block group)
* When need to fetch **statistical time series** for a region
* When need **comparisons across places**, such as counties in a state.


## How to Use

### Step 1: Import and Initialize the Client

Use an **API Key** from the Data Commons portal for V2 access.

```
    import streamlit as st
    from datacommons_client.client import DataCommonsClient                                                                                                
    # Initialize the client with the API Key
    client = DataCommonsClient(st.secrets["DC_API_KEY"])
```

### Step 2: Resolve one or multiple place names oto DCIDs

#### Example: Resolve a Place Name to its DCID

```
    # use 'fetch_dcids_by_name' inside 'client.resolve'
    # This returns a ResolveResponse object, not a DataFrame directly  
    response = client.resolve.fetch_dcids_by_name(names=["San Diego County"])                                                           
    # Convert response to a dictionary for easier access  
    result_dict = response.to_dict() 
    
    # Extract the DCID                        
    # The structure is: entities -> candidates -> dcid 
    if result_dict.get('entities'):           
        candidates = result_dict['entities'][0].get('candidates')  
        if candidates:                         
            san_diego_dcid = candidates[0]['dcid']  
            print(f"Resolved DCID: {san_diego_dcid}")                 
```

### Step 3: Find Correct Variables

```
search_results = client.observation.fetch_available_statistical_variables( 
    entity_dcids=[san_diego_dcid]  # or whatever entity you're interested in 
)                                                                                                                                                
if search_results:
    for entity_dcid, variables in search_results.items():
        print(f"\nEntity: {entity_dcid}")
        for var in variables:
            print(f"            DCID: {var}")
else:                                         
    print("No variables found.")
```      

Please note that a place like San Diego county may have more than 150000 variables. Better to filter the returned variables by some keywords and then decide which should be used in the next step. 


### Step 4: Fetch Stats

The core functions for data retrieval is `observations_dataframe()`.

#### Example: Get Statistical Observations as a DataFrame

The `observations_dataframe` method retrieves time-series data for a variable/entity pair.

```
    # Fetch the population of San Diego county 
    df = client.observations_dataframe(
        variable_dcids=["Count_Person"],
        entity_dcids=[san_diego_dcid],
        date="latest" # Get the most recent value
    )
```
