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

### 2. Use the Query Function

```python
# Configuration
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
    Load FRS facilities for a specified state and NAICS industry.

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
    if state not in ALLOWED_STATES:
        raise ValueError(f"Invalid state '{state}'. Allowed: {ALLOWED_STATES}")
    if naics_name not in ALLOWED_NAICS:
        raise ValueError(f"Invalid NAICS '{naics_name}'. Allowed: {ALLOWED_NAICS}")

    endpoint_url = "https://frink.apps.renci.org/qlever-geo/sparql"

    # SPARQL query (validated for Qlever - do not modify)
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

## Important Notes

- Do not modify the SPARQL query; it's validated for Qlever
- Function only works for Illinois, Maine, and Ohio
- Returns up to 1000 facilities by default (adjustable via `limit` parameter)
