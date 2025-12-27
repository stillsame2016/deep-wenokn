"""
FRS Facilities Utilities

Pre-validated functions for querying EPA's Facility Registry Service (FRS)
data from the SAWGraph knowledge graph.

DO NOT MODIFY THIS FILE - Functions are validated against specific SPARQL endpoints.
"""

import json
import requests
import geopandas as gpd
import sparql_dataframe
from shapely import wkt
from shapely.ops import linemerge
from shapely.geometry import Point

def load_FRS_facilities(state: str, naics_name: str, limit: int = 1000) -> gpd.GeoDataFrame:
    """
    Load FRS facilities for a specified state and NAICS industry.
    
    This function queries the SAWGraph knowledge graph via Qlever SPARQL endpoint
    to retrieve EPA FRS facility data with geometries.

    Args:
        state: State name - must be one of: "Illinois", "Maine", "Ohio"
        naics_name: NAICS industry name - must be from ALLOWED_NAICS list:
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
        limit: Maximum number of facilities to retrieve (default: 1000)

    Returns:
        GeoDataFrame with facility geometries and attributes including:
        - facilityName: Name of the facility
        - industryCodes: Industry classifications (comma-separated if multiple)
        - geometry: Point geometry in EPSG:4326
        - countyName: County name
        - stateName: State name
        - frsId: FRS identifier (if available)
        - triId: TRI identifier (if available)
        - rcraId: RCRA identifier (if available)
        - airId: Air program identifier (if available)
        - npdesId: NPDES identifier (if available)
        - envInterestTypes: Environmental interest types (if available)
        - facility: Facility URI

    Raises:
        ValueError: If state or NAICS name is not in the allowed lists

    Example:
        >>> sewage = load_FRS_facilities("Maine", "Sewage Treatment")
        >>> print(f"Found {len(sewage)} facilities")
        >>> print(sewage.head())
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

    # SPARQL query validated for Qlever endpoint
    # The double braces {{ }} are f-string escapes that become single braces in SPARQL
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

    # Return as GeoDataFrame with WGS84 coordinate system
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")


def get_upstream_subwatersheds(river_gdf):
    """
    Given a GeoDataFrame containing a river geometry, return a GeoDataFrame
    of all upstream HUC12 sub-watersheds using the USGS WBD HUC12
    ArcGIS Feature Service.
    """
    HUC12_FS_URL = "https://services.arcgis.com/P3ePLMYs2RVChkJx/ArcGIS/rest/services/Watershed_Boundary_Dataset_HUC_12s/FeatureServer/0/query"
        
    # 1. Ensure CRS is EPSG:4326
    if river_gdf.crs is None:
        raise ValueError("river_gdf must have a CRS defined")
    if river_gdf.crs.to_epsg() != 4326:
        river_gdf = river_gdf.to_crs(epsg=4326)
    
    # 2. Get the river geometry
    river_geom = river_gdf.geometry.iloc[0]
    river_name = river_gdf['riverName'].iloc[0] if 'riverName' in river_gdf.columns else "Unknown River"
    
    print(f"Finding watersheds for: {river_name}")
    print(f"River bounds: {river_gdf.total_bounds}")
    
    # 3. Query all HUC12s that intersect the river geometry
    print("\nQuerying HUC12s that intersect the river...")
    
    bounds = river_gdf.total_bounds  # minx, miny, maxx, maxy
    params = {
        "geometry": json.dumps({
            "xmin": bounds[0],
            "ymin": bounds[1],
            "xmax": bounds[2],
            "ymax": bounds[3],
            "spatialReference": {"wkid": 4326}
        }),
        "geometryType": "esriGeometryEnvelope",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "huc12,tohuc,name",
        "returnGeometry": "true",
        "outSR": 4326,
        "f": "geojson"
    }
    
    r = requests.get(HUC12_FS_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    
    if "error" in data:
        raise RuntimeError(f"API Error: {data['error']}")
    
    features = data.get("features", [])
    print(f"Found {len(features)} HUC12s in river bounds")
    
    if not features:
        raise RuntimeError("No HUC12s found intersecting river bounds")
    
    # Convert to GeoDataFrame
    all_hucs_gdf = gpd.GeoDataFrame.from_features(data, crs="EPSG:4326")
    
    # 4. Find which HUC12s actually intersect the river line
    all_hucs_gdf['intersects_river'] = all_hucs_gdf.geometry.intersects(river_geom)
    river_hucs = all_hucs_gdf[all_hucs_gdf['intersects_river']].copy()
    
    print(f"Found {len(river_hucs)} HUC12s that intersect the river geometry")
    
    if len(river_hucs) == 0:
        raise RuntimeError("No HUC12s intersect the river geometry")
    
    # 5. Identify the primary watershed by finding the most common HUC prefix
    # Group by HUC8 (first 8 digits) to find the main watershed
    river_hucs['huc8'] = river_hucs['huc12'].str[:8]
    huc8_counts = river_hucs['huc8'].value_counts()
    
    print(f"\nHUC8 watersheds intersected:")
    for huc8, count in huc8_counts.items():
        print(f"  {huc8}: {count} HUC12s")
    
    # Use the HUC8 with the most HUC12s as the primary watershed
    primary_huc8 = huc8_counts.idxmax()
    print(f"\nPrimary watershed: HUC8 {primary_huc8}")
    
    # Filter to only HUC12s in the primary watershed
    river_hucs_filtered = river_hucs[river_hucs['huc8'] == primary_huc8].copy()
    print(f"Filtered to {len(river_hucs_filtered)} HUC12s in primary watershed")
    
    river_huc_codes = set(river_hucs_filtered['huc12'].values)
    
    # 6. Find the most downstream HUC12 in the primary watershed
    terminal_candidates = []
    for idx, row in river_hucs_filtered.iterrows():
        tohuc = row.get('tohuc', '')
        # Terminal if TOHUC is empty, or points outside the primary watershed
        if not tohuc or str(tohuc).strip() == '' or tohuc not in river_huc_codes:
            terminal_candidates.append(row)
    
    if terminal_candidates:
        terminal_huc12 = terminal_candidates[0]['huc12']
        terminal_name = terminal_candidates[0].get('name', 'N/A')
        print(f"\nTerminal HUC12: {terminal_huc12} - {terminal_name}")
    else:
        print(f"\nNo clear terminal found, using all {len(river_huc_codes)} HUC12s as starting points")
    
    # 7. Start with all HUC12s that the river touches in the primary watershed
    upstream = river_huc_codes.copy()
    to_process = list(river_huc_codes)
    processed = set()
    
    print(f"\nTraversing upstream from {len(river_huc_codes)} river HUC12s...")
    
    max_iterations = 10000
    iteration = 0
    
    while to_process and iteration < max_iterations:
        iteration += 1
        current_huc = to_process.pop(0)
        
        if current_huc in processed:
            continue
        
        processed.add(current_huc)
        
        if iteration % 100 == 0:
            print(f"  Processed {iteration} nodes, found {len(upstream)} watersheds...")
        
        # Find all HUC12s that drain TO this one
        params = {
            "where": f"tohuc = '{current_huc}'",
            "outFields": "huc12,tohuc",
            "returnGeometry": "false",
            "f": "json"
        }
        
        try:
            r = requests.get(HUC12_FS_URL, params=params, timeout=30)
            r.raise_for_status()
            
            for feat in r.json().get("features", []):
                h = feat["attributes"]['huc12']
                # Only include if it's in the same HUC8 watershed
                if h.startswith(primary_huc8) and h not in upstream:
                    upstream.add(h)
                    to_process.append(h)
        except Exception as e:
            print(f"Warning: Failed to get upstream HUCs for {current_huc}: {e}")
    
    if iteration >= max_iterations:
        print(f"Warning: Reached maximum iteration limit")
    
    print(f"Found {len(upstream)} total upstream HUC12 watersheds in HUC8 {primary_huc8}")
    
    # 8. Fetch geometries for all upstream HUC12s
    def chunks(lst, n=20):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]
    
    all_features = []
    batch_num = 0
    for batch in chunks(list(upstream)):
        batch_num += 1
        where = f"huc12 IN ({','.join(repr(h) for h in batch)})"
        params = {
            "where": where,
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson"
        }
        
        try:
            r = requests.get(HUC12_FS_URL, params=params, timeout=30)
            r.raise_for_status()
            geojson_data = r.json()
            if "features" in geojson_data:
                all_features.extend(geojson_data["features"])
                if batch_num % 10 == 0:
                    print(f"  Batch {batch_num}: Retrieved {len(all_features)} features so far...")
        except Exception as e:
            print(f"Warning: Failed to get batch {batch_num}: {e}")
    
    print(f"Total features retrieved: {len(all_features)}")
    
    # 9. Convert to GeoDataFrame
    huc12_gdf = gpd.GeoDataFrame.from_features(all_features, crs="EPSG:4326")
    return huc12_gdf
