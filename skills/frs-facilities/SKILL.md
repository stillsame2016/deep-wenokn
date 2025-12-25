---
name: frs-facilities
description: Use this skill for requests related to the geometry definitions of the facilities listed in EPA's Facility Registry Service (FRS) in Illinois, Maine, and Ohio; it provides a way to get the geometries of FRS facilities as a GeoDataframe.
---

# FRS-Facilities Skill

## Description

This skill gets the geometries of FRS facilities in USA by querying SAWGraph knowledge graph on FRINK.

## When to Use

- Find a FRS facility by name
- Find FRS facilities within a region
- Find FRS facilities with spatial relation with other objects

## How to Use

### Step 1: Choose one NAICS code from the following list:

    Waste Treatment and Disposal,
    Converted Paper Manufacturing,
    Water Supply and Irrigation,
    Sewage Treatment,
    Plastics Product Manufacturing,
    Textile and Fabric Finishing and Coating,
    Basic Chemical Manufacturing,
    Paint, Coating, and Adhesive Manufacturing,
    Aerospace Product and Parts,
    Drycleaning and Laundry Services,
    Carpet and Upholstery Cleaning Services,
    Solid Waste Landfill,


### Step 2: Use the following function to get desired FRS facilities

```python
# Allowed states and NAICS industries
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

def load_FRS_facilities(state: str, naics_name: str, limit: int = 1000) -> gpd.GeoDataFrame:
    """
    Load facilities from the FRS dataset for a given state and NAICS industry name.

    Parameters:
        state (str): State name, e.g., "Illinois", "Maine", "Ohio".
        naics_name (str): NAICS industry name, e.g., "Waste Treatment and Disposal".
        limit (int): Maximum number of facilities to fetch (default 1000).

    Returns:
        gpd.GeoDataFrame: Facilities with geometry and other attributes.
    """

    # Validate parameters
    if state not in ALLOWED_STATES:
        raise ValueError(f"Invalid state '{state}'. Allowed states: {ALLOWED_STATES}")
    if naics_name not in ALLOWED_NAICS:
        raise ValueError(f"Invalid NAICS name '{naics_name}'. Allowed values: {ALLOWED_NAICS}")

    endpoint_url = "https://frink.apps.renci.org/qlever-geo/sparql"

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
    # Fetch data
    df = sparql_dataframe.get(endpoint_url, query)

    # Convert WKT to geometry
    df = df.dropna(subset=["facilityWKT"]).copy()
    df["geometry"] = df["facilityWKT"].apply(wkt.loads)
    df = df.drop(columns=["facilityWKT"])

    # Convert to GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    # gdf = gdf.drop_duplicates(subset='geometry')  
    return gdf
```
