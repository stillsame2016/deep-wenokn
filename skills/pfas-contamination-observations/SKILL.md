---
name: pfas-contamination-observations
description: Use this skill for the requests related to the geometry definitions of PFAS contamination observations in Maine; it provides a way to get the geometries of PFAS contamination observations as a GeoDataframe. 
---

# PFAS-Contamination-Observations Skill

## Description

This skill gets the geometries of PFAS contamination observations in Maine by quering SWAGraph knowledge graph on FRINK. Note that it doesn't have PFAS contamination observations out of Maine now.

## When to Use

- Find PFAS contamination observations in a region
- Find PFAS contamination observations with spatial conditions

## How to Use

### Example: Get all PFAS contamination observations in Maine:

```
pip install sparql_dataframe
```

```
import sparql_dataframe

def load_PFAS_contamiation_observations() -> gpd.GeoDataFrame:
    """
    Fetch PFAS contaminant samples exceeding thresholds and return as GeoDataFrame.
    """

    endpoint_url = "https://frink.apps.renci.org/federation/sparql"
    query = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>
PREFIX coso: <http://w3id.org/coso/v1/contaminoso#>
PREFIX qudt: <http://qudt.org/schema/qudt#>

SELECT ?wkt
       (SAMPLE(?observation) AS ?Obs)
       (SAMPLE(?substance) AS ?Substance)
       (MAX(?obsDate) AS ?Date)
       (SAMPLE(?result_value) AS ?Value)
       (SAMPLE(?unit) AS ?Unit)
       (SAMPLE(?samplePoint) AS ?SamplePoint)
WHERE {
  ?observation rdf:type coso:ContaminantObservation ;
               coso:observedAtSamplePoint ?samplePoint ;
               coso:ofSubstance ?substance ;
               coso:hasResult ?result ;
               coso:observedTime ?obsDate .

  ?samplePoint rdf:type coso:SamplePoint ;
               geo:hasGeometry/geo:asWKT ?wkt .

  ?result coso:measurementValue ?result_value ;
          coso:measurementUnit ?unit .

   VALUES (?substanceVal ?limitVal ?unitVal) {
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFOS_A> 4 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFOA_A> 4 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFNA_A> 10 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFHXA_A> 10 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFBS_A> 10 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFTEA_A> 10 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFOS> 4 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
    (<http://sawgraph.spatialai.org/v1/me-egad#parameter.PFOA> 4 <http://qudt.org/vocab/unit/NanoGM-PER-L>)
  }

  FILTER(?substance = ?substanceVal && ?unit = ?unitVal && ?result_value > ?limitVal)
}
GROUP BY ?wkt
"""
    
    df = sparql_dataframe.get(endpoint_url, query)

    # Convert WKT to geometry
    if "wkt" in df.columns:
        df = df.dropna(subset=["wkt"]).copy()
        df["geometry"] = df["wkt"].apply(wkt.loads)
        df = df.drop(columns=["wkt"])
    else:
        df["geometry"] = None

    # Optionally add medium
    def get_medium(unit):
        if unit == "http://sawgraph.spatialai.org/v1/me-egad#unit.NG-G":
            return "soil/tissue"
        elif unit == "http://qudt.org/vocab/unitNanoGM-PER-L":
            return "water"
        else:
            return "unknown"

    df["medium"] = df["Unit"].apply(get_medium)
    
    gdf = gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")
    return gdf    
```
