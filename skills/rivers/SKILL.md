---
name: rivers
description: Use this skill for the requests related to the geometry definitions of rivers in USA; it provides a way to get the geometries of rivers as a GeoDataframe. 
---

# Rivers Skill

## Description

This skill gets the geometries of rivers in USA by quering GeoConnex knowledge graph on FRINK using their names.

## When to Use

- Find river geometries by names
- Find rivers intersecting with a region
- Find rivers with spatial relation with other objects
- Find all counties a river flows through

## How to Use

### Step 1: Construct a SPARQL query

The following SPARQL gets the river geometry by a name.

```
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>

SELECT DISTINCT ?riverName ?riverGeometry 
WHERE {{
  ?river a hyf:HY_FlowPath ;
         a hyf:HY_WaterBody ;
         a schema:Place ;
         schema:name ?riverName ;
         geo:hasGeometry/geo:asWKT ?riverGeometry .
  FILTER(LCASE(?riverName) = LCASE("{river_name}")) .
}}
ORDER BY DESC(STRLEN(?riverGeometry))
LIMIT 1
```

Note a river name must be complete, for example, 'Muskingum River' or 'Rose Creek'. 

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

### Example 1: Find all rivers in a county

**User Request:** "Find all rivers in Ross county, Ohio"

**Approach:**

Use the following SPARQL query in the first step:

```
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX kwgr: <http://stko-kwg.geog.ucsb.edu/lod/resource/>
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?riverName ?riverGeometry
WHERE {{
    ?county rdf:type kwg-ont:AdministrativeRegion_2 ;
                    rdfs:label ?countyName ;
                    geo:hasGeometry/geo:asWKT ?countyGeometry.
    FILTER(STRSTARTS(STR(?county), STR(kwgr:)))
    FILTER(STRSTARTS(LCASE(?countyName), LCASE("Ross County, Ohio")))

  ?river a hyf:HY_FlowPath ;
         a hyf:HY_WaterBody ;
         a schema:Place ;
         schema:name ?riverName ;
         geo:hasGeometry/geo:asWKT ?riverGeometry .
   
   FILTER(geof:sfIntersects(?riverGeometry, ?countyGeometry)) .
}}
LIMIT 300
```

Note that a county name must use the format like "Ross County" (a county name only) or "Ross County, Ohio" (a county name with a state name).

### Example 2: Find all rivers in a state

**User Request:** "Find all rivers in Ohio State"

**Approach:**

Use the following SPARQL query in the first step:

```
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX kwgr: <http://stko-kwg.geog.ucsb.edu/lod/resource/>
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?riverName ?riverGeometry
WHERE {{
  ?state rdf:type kwg-ont:AdministrativeRegion_1 ;
         rdfs:label ?stateName ;
         geo:hasGeometry/geo:asWKT ?stateGeometry .
  FILTER(STRSTARTS(STR(?state), STR(kwgr:)))
  FILTER(STRSTARTS(LCASE(?stateName), LCASE("Ohio")))

  ?river a hyf:HY_FlowPath ;
         a hyf:HY_WaterBody ;
         a schema:Place ;
         schema:name ?riverName ;
         geo:hasGeometry/geo:asWKT ?riverGeometry .

  FILTER(geof:sfIntersects(?riverGeometry, ?stateGeometry))
  FILTER(BOUND(?riverName) && STRLEN(LCASE(STR(?riverName))) > 0)
}}
LIMIT 2000
```

### Example 2: Find all counties that a specific river passes

**User Request:** "Find all counties that Ohio river passes"

**Approach:**

Use the following SPARQL query in the first step:

```
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX kwgr: <http://stko-kwg.geog.ucsb.edu/lod/resource/>
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?countyName ?countyGeometry 
WHERE {
  ?river a hyf:HY_FlowPath ;
         a hyf:HY_WaterBody ;
         a schema:Place ;
         schema:name ?riverName ;
         geo:hasGeometry/geo:asWKT ?riverGeometry .
  FILTER(LCASE(?riverName) = LCASE("Ohio River")) .
  
  ?county rdf:type kwg-ont:AdministrativeRegion_2 ;
          rdfs:label ?countyName ;
          geo:hasGeometry/geo:asWKT ?countyGeometry .
  FILTER(STRSTARTS(STR(?county), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))
  
  FILTER(geof:sfIntersects(?riverGeometry, ?countyGeometry))
}
LIMIT 200
```

### Example 4: Find all states that a specific river passes

**User Request:** "Find all states that Ohio river passes"

**Approach:**

Use the following SPARQL query in the first step:

```
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX geof: <http://www.opengis.net/def/function/geosparql/>
PREFIX kwg-ont: <http://stko-kwg.geog.ucsb.edu/lod/ontology/>
PREFIX kwgr: <http://stko-kwg.geog.ucsb.edu/lod/resource/>
PREFIX hyf: <https://www.opengis.net/def/schema/hy_features/hyf/>
PREFIX schema: <https://schema.org/>

SELECT DISTINCT ?stateName ?stateGeometry 
WHERE {
  ?river a hyf:HY_FlowPath ;
         a hyf:HY_WaterBody ;
         a schema:Place ;
         schema:name ?riverName ;
         geo:hasGeometry/geo:asWKT ?riverGeometry .
  FILTER(LCASE(?riverName) = LCASE("Ohio River")) .
  
  ?state rdf:type kwg-ont:AdministrativeRegion_1 ;
          rdfs:label ?stateName ;
          geo:hasGeometry/geo:asWKT ?stateGeometry .
  FILTER(STRSTARTS(STR(?state), "http://stko-kwg.geog.ucsb.edu/lod/resource/"))
  FILTER(strlen(?stateName) > 2)

  FILTER(geof:sfIntersects(?riverGeometry, ?stateGeometry))
}
LIMIT 200
```
                       
## Notes 

- To find all downstream counties of a river starting from a specific object near the river, first identify all counties that the river flows through, and then determine which of those counties are downstream.
- Unless explicitly stated, do not assume FRINK contains other types of data.   
