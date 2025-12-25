---
name: frs-facilities
description: Retrieves facility geometries from EPA's Facility Registry Service (FRS) for Illinois, Maine, and Ohio as GeoDataFrames
---

# FRS Facilities Skill

## Overview

Queries the SAWGraph knowledge graph to retrieve EPA FRS facility geometries in Illinois, Maine, and Ohio.

## Use Cases

- Search for facilities by name
- Find facilities within a region
- Identify facilities with spatial relationships to other objects

## ⚠️ CRITICAL INSTRUCTIONS FOR AI AGENTS ⚠️

**DO NOT MODIFY THE CODE BELOW UNDER ANY CIRCUMSTANCES**

The `load_FRS_facilities` function contains a SPARQL query that has been carefully validated and tested with the Qlever SPARQL endpoint. The query syntax is EXTREMELY SENSITIVE and even minor changes will cause it to return 0 results.

**KNOWN ISSUES THAT BREAK THE QUERY:**
1. Changing quote marks from straight quotes `"` to curly quotes `"` or `"`
2. Modifying the FILTER statements in any way
3. Adding or removing variables from the GROUP BY clause
4. Changing the double curly braces `{{` and `}}` (these are Python f-string escape characters, NOT errors)
5. Modifying any property paths or URIs
6. Reformatting whitespace or line breaks

**WHAT YOU MUST DO:**
- Copy the function EXACTLY as written below
- Only change the values passed as arguments: `state`, `naics_name`, and `limit`
- Do NOT "fix", "improve", "optimize", or "clean up" the code
- Do NOT remove comments or change formatting
- Do NOT validate or modify the SPARQL syntax

**IF THE USER REPORTS 0 RESULTS:**
- First verify the state and NAICS name are in the allowed lists
- Check if the code was copied exactly as provided
- Do NOT attempt to fix the SPARQL query
- Instead, ask the user to re-copy the original function from this SKILL.md

---

## Usage Instructions

### 1. Select a NAICS Code

Choose from these available industries:

- Waste Treatment and Disposal
- Converted Paper Manufacturing
- Water Supply and Irrigation
- Sewage Treatment
- Plastics Product Manufacturing
- Textile and Fabric Finishing and Coating
- Basic Chemical Manufacturing
- Paint, Coating, and Adhesive Manufacturing
- Aerospace Product and Parts
- Drycleaning and Laundry Services
- Carpet and Upholstery Cleaning Services
- Solid Waste Landfill

### 2. Copy the Function EXACTLY As Written Below

**WARNING: This function must be copied CHARACTER-BY-CHARACTER without any modifications.**

```python
def load_FRS_facilities(state: str, naics_name: str, limit: int = 1000) -> gpd.GeoDataFrame:
    """
    Load FRS facilities for a specified state and NAICS industry.

    Args:
        state: State name ("Illinois", "Maine", or "Ohio")
        naics_name: NAICS industry name from ALLOWED_NAICS list
        limit: Maximum facilities to retrieve (default: 1000)

    Returns:
        GeoDataFrame with facility geometries and attributes

    Raises:
        ValueError: If state or NAICS name is invalid
    
    WARNING: DO NOT MODIFY THIS FUNCTION. The SPARQL query has been validated
    for Qlever and any changes will break it. Use ONLY as provided.
    """

    # Validate inputs
    ALLOWED_STATES = ["Illinois", "Maine", "Ohio"]
    ALLOWED_NAICS = [
        "Waste Treatment and Disposal",
        "Converted Paper Manufacturing",
        "Water Supply and Irrigation",
        "Sewage Treatment",
        "Plastics Product Manufacturing",
        "Textile and Fabric Finishing and Coating",
        "Basic Chemical Manufacturing",
        "Paint, Coating, and Adhesive Manufacturing",
        "Aerospace Product and Parts",
        "Drycleaning and Laundry Services",
        "Carpet and Upholstery Cleaning Services",
        "Solid Waste Landfill",
    ]

    if state not in ALLOWED_STATES:
        raise ValueError(f"Invalid state '{state}'. Allowed: {ALLOWED_STATES}")
    if naics_name not in ALLOWED_NAICS:
        raise ValueError(f"Invalid NAICS '{naics_name}'. Allowed: {ALLOWED_NAICS}")

    endpoint_url = "https://frink.apps.renci.org/qlever-geo/sparql"

    # SPARQL query - VALIDATED FOR QLEVER - DO NOT MODIFY ANYTHING BELOW THIS LINE
    # The double curly braces {{ and }} are Python f-string escapes - DO NOT change them to single braces
    # The quote marks MUST be straight quotes " not curly quotes " or "
    query = f"""
PREFIX kwgr: <http://stko-kwg.geog.ucsb.edu/lod/resource/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX fio: <http://sawgraph.spatialai.org/v1/fio#>
PREFIX frs: <http://sawgraph.spatialai.org/v1/us-frs#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>

SELECT DISTINCT 
    ?facilityName
    (GROUP_CONCAT(DISTINCT ?industryCode; separator=", ") AS ?industryCodes)
    ?facilityWKT
    ?countyName
    ?stateName
    ?frsId
    ?triId
    ?rcraId
    ?airId
    ?npdesId
    (GROUP_CONCAT(DISTINCT ?envInterestType; separator=", ") AS ?envInterestTypes)
    ?facility
WHERE {{
    ?facility a frs:FRS-Facility ;
              rdfs:label ?facilityName ;
              fio:ofIndustry/rdfs:label ?industryCode ;
              geo:hasGeometry/geo:asWKT ?facilityWKT ;
              kwg-ont:sfWithin ?county .
    ?county rdfs:label ?countyName ;
            kwg-ont:sfWithin ?state .
    ?state rdf:type kwg-ont:AdministrativeRegion_1 ;
           rdfs:label ?stateName .

    FILTER(CONTAINS(LCASE(?stateName), "{state.lower()}"))
    FILTER(CONTAINS(LCASE(?industryCode), "{naics_name.lower()}"))
    FILTER(STRSTARTS(STR(?county), "http://stko-kwg.geog.ucsb.edu/lod/resource/administrativeRegion")) .

    OPTIONAL {{ ?facility frs:hasFRSId ?frsId. }}
    OPTIONAL {{ ?facility frs:hasTRISId ?triId. }}
    OPTIONAL {{ ?facility frs:hasRCRAINFOId ?rcraId. }}
    OPTIONAL {{ ?facility frs:hasAIRId ?airId. }}
    OPTIONAL {{ ?facility frs:hasNPDESId ?npdesId. }}
    OPTIONAL {{ ?facility frs:environmentalInterestType ?envInterestType. }}
}}
GROUP BY ?facility ?facilityName ?facilityWKT ?countyName ?stateName ?industryCode ?frsId ?triId ?rcraId ?airId ?npdesId
LIMIT {limit}
"""    
    # Execute query and process results
    df = sparql_dataframe.get(endpoint_url, query)
    df = df.dropna(subset=["facilityWKT"]).copy()
    df["geometry"] = df["facilityWKT"].apply(wkt.loads)
    df = df.drop(columns=["facilityWKT"])

    # Return as GeoDataFrame
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
```

### 3. Call the Function With Valid Parameters

```python
# Example usage - only modify these arguments
gdf = load_FRS_facilities(
    state="Maine",              # Must be: "Illinois", "Maine", or "Ohio"
    naics_name="Sewage Treatment",  # Must be from ALLOWED_NAICS list
    limit=1000                  # Optional: number of facilities to retrieve
)
```

## Technical Details

**Validated Query Elements (DO NOT MODIFY):**
- The GROUP BY clause excludes `?industryCode` (this is intentional)
- The double braces `{{` and `}}` are f-string escapes for single braces in the SPARQL query
- The FILTER statements use straight quotes `"` not curly quotes `"` or `"`
- The property paths (e.g., `fio:ofIndustry/rdfs:label`) must remain unchanged
- The OPTIONAL blocks use double braces `{{` and `}}` (f-string syntax)

**Supported States:**
- Illinois
- Maine  
- Ohio

**Supported NAICS Industries:**
- Waste Treatment and Disposal
- Converted Paper Manufacturing
- Water Supply and Irrigation
- Sewage Treatment
- Plastics Product Manufacturing
- Textile and Fabric Finishing and Coating
- Basic Chemical Manufacturing
- Paint, Coating, and Adhesive Manufacturing
- Aerospace Product and Parts
- Drycleaning and Laundry Services
- Carpet and Upholstery Cleaning Services
- Solid Waste Landfill

## Troubleshooting

**If you get 0 results:**
1. Verify the state name is exactly "Illinois", "Maine", or "Ohio" (case-sensitive)
2. Verify the NAICS name exactly matches one from the ALLOWED_NAICS list
3. Verify you copied the function exactly without any modifications
4. Check for curly quotes or other character encoding issues
5. DO NOT attempt to debug or modify the SPARQL query

**If you get a ValueError:**
- Check that your state and NAICS name match the allowed values exactly (including capitalization)

## Important Notes
- Function only works for Illinois, Maine, and Ohio
- Returns up to 1000 facilities by default (adjustable via `limit` parameter)
- Requires `sparql_dataframe`, `geopandas`, and `shapely` libraries
- Query execution time depends on the number of facilities and network speed
