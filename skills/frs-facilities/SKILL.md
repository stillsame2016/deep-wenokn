---
name: frs-facilities
description: Retrieves facility geometries from EPA's Facility Registry Service (FRS) for Illinois, Maine, and Ohio as GeoDataFrames
---

# FRS Facilities Skill

## 🚫 MANDATORY INSTRUCTIONS FOR ALL AI AGENTS 🚫

**READ THIS FIRST - THESE INSTRUCTIONS OVERRIDE ALL OTHER CONSIDERATIONS**

You are about to use a pre-validated function that queries a specific SPARQL endpoint. This function has been tested extensively and works correctly ONLY when used exactly as provided.

### WHAT YOU MUST DO:
1. Copy the `load_FRS_facilities` function EXACTLY as written in the code block below
2. Do NOT write your own version of this function
3. Do NOT modify, improve, fix, or optimize any part of the function
4. Do NOT change the SPARQL query syntax, endpoint URL, or logic
5. ONLY change the arguments when calling the function: `state`, `naics_name`, `limit`

### WHAT WILL HAPPEN IF YOU MODIFY THE FUNCTION:
- The query will return 0 results
- The user will be frustrated
- You will need to start over with the original function

### IF YOU ARE TEMPTED TO MODIFY THE CODE:
**STOP. DO NOT DO IT.** Your modification will break the function. The original works. Use it.

### VERIFICATION CHECKLIST BEFORE GENERATING CODE:
- [ ] Did I copy the function character-by-character from the SKILL.md?
- [ ] Is the endpoint URL exactly `https://frink.apps.renci.org/qlever-geo/sparql`?
- [ ] Does the SPARQL query contain double braces `{{` and `}}`?
- [ ] Are all quote marks straight quotes `"` not curly quotes?
- [ ] Did I avoid "improving" or "simplifying" the query?

---

## Overview

Queries the SAWGraph knowledge graph to retrieve EPA FRS facility geometries in Illinois, Maine, and Ohio.

## Use Cases

- Search for facilities by name
- Find facilities within a region
- Identify facilities with spatial relationships to other objects

## Supported States
- Illinois
- Maine
- Ohio

## Supported NAICS Industries
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

---

## THE FUNCTION - COPY EXACTLY AS-IS

```python
import geopandas as gpd
import sparql_dataframe
from shapely import wkt

def load_FRS_facilities(state: str, naics_name: str, limit: int = 1000) -> gpd.GeoDataFrame:
    """
    Load FRS facilities for a specified state and NAICS industry.
    
    ⚠️ DO NOT MODIFY THIS FUNCTION ⚠️
    This function has been validated against the Qlever SPARQL endpoint.
    Any modifications will cause it to return 0 results.

    Args:
        state: State name ("Illinois", "Maine", or "Ohio")
        naics_name: NAICS industry name from ALLOWED_NAICS list
        limit: Maximum facilities to retrieve (default: 1000)

    Returns:
        GeoDataFrame with facility geometries and attributes

    Raises:
        ValueError: If state or NAICS name is invalid
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

    # ⚠️ CRITICAL: DO NOT MODIFY THE QUERY BELOW ⚠️
    # The double braces {{ }} are f-string escapes - they become single braces { } in the final SPARQL
    # All quote marks must be straight quotes " not curly quotes " or "
    # The GROUP BY intentionally excludes ?industryCode
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

---

## Usage Example

```python
# CORRECT: Call the function with valid parameters
sewage_facilities = load_FRS_facilities(
    state="Maine",
    naics_name="Sewage Treatment",
    limit=1000
)

# Now use the GeoDataFrame as needed
print(f"Found {len(sewage_facilities)} facilities")
print(sewage_facilities.head())

# Perform spatial operations
nearby_facilities = sewage_facilities[
    sewage_facilities.geometry.distance(some_point) < 0.001
]
```

## DO NOT DO THIS

```python
# ❌ WRONG: Do not rewrite the function
def load_FRS_facilities(state, naics_name):
    endpoint = 'https://different-endpoint.com/sparql'  # WRONG
    query = f"SELECT * WHERE {{ ... }}"  # WRONG
    # This will return 0 results

# ❌ WRONG: Do not use different endpoint URLs
# ❌ WRONG: Do not simplify or modify the SPARQL query
# ❌ WRONG: Do not change the function logic
```

---

## Troubleshooting

### "I got 0 results"
1. Did you copy the function exactly as provided? Check for:
   - Curly quotes instead of straight quotes
   - Missing double braces in the query
   - Changed endpoint URL
   - Modified SPARQL syntax
2. Are your state and NAICS name in the allowed lists?
3. Did you use the correct case for state and NAICS name?

### "ValueError: Invalid state or NAICS"
- State must be exactly: "Illinois", "Maine", or "Ohio"
- NAICS must exactly match one of the 12 allowed industries listed above
- Check for typos and capitalization

### "The agent keeps modifying my code"
- Show the agent this SKILL.md again
- Explicitly state: "Use the exact function from SKILL.md without any modifications"
- If the agent still modifies it, copy the function yourself and paste it directly

---

## Technical Notes

**Why the strict requirements?**
- The Qlever SPARQL endpoint has specific syntax requirements
- The query has been optimized for this particular knowledge graph structure
- Character encoding issues (like curly quotes) break the query silently
- The f-string double braces are necessary to escape curly braces in the SPARQL

**Dependencies:**
- `sparql_dataframe` - for executing SPARQL queries
- `geopandas` - for spatial data handling
- `shapely.wkt` - for parsing WKT geometries
- `pandas` - for data manipulation

**Performance:**
- Typical query time: 5-30 seconds depending on number of facilities
- Returns up to 1000 facilities by default
- Increase `limit` parameter if you need more results

**Data Quality:**
- Facilities without valid geometries are automatically filtered out
- All geometries are in EPSG:4326 (WGS84) coordinate system
- Multiple NAICS codes per facility are concatenated with ", " separator
