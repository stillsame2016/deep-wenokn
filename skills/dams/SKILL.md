---
name: dams
description: Use this skill for the requests related to the geometry definitions of dams in USA; it provides a way to get the geometries of dams as a GeoDataframe. 
---

# Dams Skill

## Description

This skill gets the geometries of dams in USA by quering GeoConnex knowledge graph on FRINK using their names.

## When to Use

- Find dam geometries by names
- Find dams within a region
- Find dams on a river
- Find dams with spatial relation with other objects

## How to Use

### Step 1: Construct a SPARQL query

The following SPARQL gets the dam geometry by a name.

```
PREFIX aschema: <https://schema.ld.admin.ch/>
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry ?damDescription
WHERE {{  
    ?dam a schema:Place;
         schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName ;
         schema:description ?damDescription;
         geo:hasGeometry/geo:asWKT ?damGeometry.
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/")) 
    FILTER(STRSTARTS(LCASE(STR(?damName)), LCASE("{dam_name}")))
}}
LIMIT 1
```

### Step 2: Send the SPARQL query to the FRINK endpoint

Use the library sparql_dataframe, you can do
```
    pip install sparql_dataframe

    import sparql_dataframe
    endpoint_url = "https://frink.apps.renci.org/federation/sparql"
    df = sparql_dataframe.get(endpoint_url, query)
```
This code gets a dataframe from the SPARQL query

### Step 3: Wrap the dataframe as a GeoDataframe

```
    # Identify the WKT column automatically
    wkt_col = None
    for col in df.columns:
        # Check if the column name suggests it's a geometry column
        col_lower = col.lower()
        if 'geometry' in col_lower or 'geom' in col_lower or 'wkt' in col_lower:
            # Verify it actually contains WKT by checking if MOST values start with valid WKT types
            sample = df[col].dropna().astype(str)
            if len(sample) > 0:
                valid_wkt = sample.str.match(r'^(POINT|LINESTRING|POLYGON|MULTIPOINT|MULTILINESTRING|MULTIPOLYGON|GEOMETRYCOLLECTION)\s*\(')
                if valid_wkt.sum() / len(sample) > 0.5:  # More than 50% are valid WKT
                    wkt_col = col
                    break

    if wkt_col is None:
        raise ValueError("No WKT geometry column found in SPARQL result.")

    # Drop missing geometries
    df = df.dropna(subset=[wkt_col]).copy()

    # Convert WKT to shapely geometries
    df['geometry'] = df[wkt_col].apply(wkt.loads)

    # Create GeoDataFrame
    gdf = gpd.GeoDataFrame(df, geometry='geometry', crs="EPSG:4326")

```

## Examples

### Example 1: Find all dams in counties

**User Request:** "Find all dams in Ross County and Scioto County, Ohio"

**Approach:**

Use the following SPARQL query in the first step:

```
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry ?countyName
WHERE {
    # User-provided counties - FILTER EARLY
    VALUES ?inputCounty {
         "San Diego County"
         "Orange County, California"
         "Los Angeles County"
    }
    
    # Counties (AdministrativeRegion_2) - FILTERED BY NAME FIRST
    ?county rdf:type <http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_2> ;
            rdfs:label ?countyName ;
            geo:hasGeometry/geo:asWKT ?countyGeometry .
    FILTER(STRSTARTS(STR(?county), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))
    FILTER(STRSTARTS(LCASE(STR(?countyName)), LCASE(?inputCounty)))
    
    # Dams - ONLY AFTER COUNTIES ARE FILTERED
    ?dam schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url>;
         schema:name ?damName ;
         geo:hasGeometry/geo:asWKT ?damGeometry .
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/"))
    
    # Spatial containment - LAST, on reduced dataset
    FILTER(geof:sfContains(?countyGeometry, ?damGeometry))
}
```

### Example 2: Find dams in states

**User Request:** "Find all dams in Ohio and Kentucky"

Use the following SPARQL query in the first step:

```
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>

SELECT ?damName ?damGeometry
WHERE {
    ?dam schema:provider "https://nid.usace.army.mil"^^<https://schema.org/url> ;
         schema:name ?damName ;
         geo:hasGeometry/geo:asWKT ?damGeometry .
    FILTER(STRSTARTS(STR(?dam), "https://geoconnex.us/ref/dams/"))

    ?state rdf:type <http://stko-kwg.geog.ucsb.edu/lod/ontology/AdministrativeRegion_1> ;
           rdfs:label ?stateName ;
           geo:hasGeometry/geo:asWKT ?stateGeometry .
    FILTER(STRSTARTS(STR(?state), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))

    VALUES ?inputState {
        "Ohio"
        "Kentucky"
    }
    FILTER(STRSTARTS(LCASE(STR(?stateName)), LCASE(?inputState)))
    FILTER(geof:sfContains(?stateGeometry, ?damGeometry))
}
```

**Notes:**

Because of GIS accuracy limits, you can’t reliably find dams on a river by checking direct geometric intersections. 
A dam is stored as a point, and that point often won’t line up exactly with the river geometry. A better approach 
is to apply a 20-meter buffer around the river and then check whether the dam point falls within that buffered area.

Qlever used by FRINK doesn't support the sfBuffer function. You have to do it through geopandas. 

Querying dams in a large region may take up to one miniute time.

Unless explicitly stated, do not assume FRINK contains other types of data.
