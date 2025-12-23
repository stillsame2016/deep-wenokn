# Add these new session state variables in the initialization section (around line 38):

if "map_center" not in st.session_state:
    st.session_state.map_center = [39.8, -98.6]  # Default center of US
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 6
if "map_bounds" not in st.session_state:
    st.session_state.map_bounds = None
if "layer_visibility" not in st.session_state:
    st.session_state.layer_visibility = {}  # Dict: {layer_name: True/False}

# Then replace the display_all_layers_map() function with this version:

def display_all_layers_map():
    """Display all GeoDataFrames as layers on a single interactive Folium map."""
    if not st.session_state.geodataframes:
        st.info("No geographic data available yet. Start a conversation to generate maps!")
        return
    
    if not FOLIUM_AVAILABLE:
        st.error("⚠️ Folium not available. Install with: `pip install folium streamlit-folium`")
        return
    
    try:
        # Calculate overall bounds from all geodataframes
        all_bounds = []
        for gdf in st.session_state.geodataframes.values():
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            all_bounds.append(gdf.total_bounds)
        
        # Use stored center/zoom or calculate from bounds
        if st.session_state.map_bounds is None and all_bounds:
            min_x = min(b[0] for b in all_bounds)
            min_y = min(b[1] for b in all_bounds)
            max_x = max(b[2] for b in all_bounds)
            max_y = max(b[3] for b in all_bounds)
            
            st.session_state.map_center = [(min_y + max_y) / 2, (min_x + max_x) / 2]
            st.session_state.map_bounds = [[min_y, min_x], [max_y, max_x]]
        
        # Create the base map with stored state
        m = folium.Map(
            location=st.session_state.map_center,
            zoom_start=st.session_state.map_zoom,
            tiles=None,
            control_scale=True
        )
        
        # Add basemap options
        folium.TileLayer(
            tiles='OpenStreetMap',
            name='Street Map',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Satellite',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
            attr='Esri',
            name='Topographic',
            overlay=False,
            control=True
        ).add_to(m)
        
        folium.TileLayer(
            tiles='CartoDB positron',
            name='Light',
            overlay=False,
            control=True
        ).add_to(m)
        
        colors = [
            '#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', 
            '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC',
            '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD', 
            '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF'
        ]
        
        # Add each geodataframe as a layer
        for idx, (name, gdf) in enumerate(st.session_state.geodataframes.items()):
            # Ensure WGS84
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            
            color = colors[idx % len(colors)]
            
            # Initialize layer visibility if not set (new layers default to visible)
            if name not in st.session_state.layer_visibility:
                st.session_state.layer_visibility[name] = True
            
            # Create feature group with stored visibility
            feature_group = folium.FeatureGroup(
                name=name.replace('_', ' ').title(), 
                show=st.session_state.layer_visibility[name]
            )
            
            def style_function(feature, color=color):
                return {
                    'fillColor': color,
                    'color': color,
                    'weight': 1.5,
                    'fillOpacity': 0.4,
                }
            
            def highlight_function(feature):
                return {
                    'fillColor': '#FFFF00',
                    'color': '#000000',
                    'weight': 2,
                    'fillOpacity': 0.7,
                }
            
            # Create tooltip
            tooltip_fields = [col for col in gdf.columns if col.lower() not in ['geometry', 'geom', 'the_geom', 'shape', 'countygeometry', 'rivergeometry', 'stategeometry', 'watershedgeometry', 'damgeometry', 'plantgeometry']]
            
            if tooltip_fields:
                tooltip = folium.GeoJsonTooltip(
                    fields=tooltip_fields,
                    aliases=[f"{field}:" for field in tooltip_fields],
                    localize=True,
                    sticky=False,
                    labels=True,
                    style="""
                        background-color: white;
                        border: 1px solid black;
                        border-radius: 3px;
                        box-shadow: 3px;
                        font-size: 11px;
                        max-width: 300px;
                        max-height: 300px;
                        overflow-y: auto;
                        padding: 8px;
                    """,
                )
            else:
                tooltip = None
            
            point_marker = folium.CircleMarker(
                radius=2,
                weight=1,
                fill=True,
                fill_opacity=0.7
            )
            
            folium.GeoJson(
                gdf,
                marker=point_marker,
                style_function=style_function,
                highlight_function=highlight_function,
                tooltip=tooltip,
                name=name.replace('_', ' ').title()
            ).add_to(feature_group)
            
            feature_group.add_to(m)
        
        # Add controls
        layer_control = folium.LayerControl(position='topright', collapsed=False)
        layer_control.add_to(m)
        
        custom_css = """
        <style>
        .leaflet-control-layers {
            font-size: 11px !important;
        }
        .leaflet-control-layers-base label,
        .leaflet-control-layers-overlays label {
            font-size: 11px !important;
            padding: 2px 5px !important;
        }
        .leaflet-control-layers-base,
        .leaflet-control-layers-overlays {
            line-height: 1.3 !important;
        }
        </style>
        """
        m.get_root().html.add_child(folium.Element(custom_css))
        
        plugins.Fullscreen(
            position='topleft',
            title='Fullscreen',
            title_cancel='Exit Fullscreen',
            force_separate_button=True
        ).add_to(m)
        
        plugins.MousePosition().add_to(m)
        
        # Only fit bounds if we haven't stored a custom view
        if st.session_state.map_bounds and all_bounds:
            m.fit_bounds(st.session_state.map_bounds, padding=[50, 50])
        
        # Display the map and capture state
        map_data = st_folium(
            m,
            width=None,
            height=500,
            returned_objects=["bounds", "zoom", "center"],
            use_container_width=True
        )
        
        # Store the map state for next time
        if map_data:
            if map_data.get("center"):
                st.session_state.map_center = [
                    map_data["center"]["lat"],
                    map_data["center"]["lng"]
                ]
            if map_data.get("zoom"):
                st.session_state.map_zoom = map_data["zoom"]
            if map_data.get("bounds"):
                bounds = map_data["bounds"]
                st.session_state.map_bounds = [
                    [bounds["_southWest"]["lat"], bounds["_southWest"]["lng"]],
                    [bounds["_northEast"]["lat"], bounds["_northEast"]["lng"]]
                ]
        
        # Display map legend
        with st.expander("🎨 Map Legend", expanded=False):
            for idx, name in enumerate(st.session_state.geodataframes.keys()):
                color = colors[idx % len(colors)]
                visibility_icon = "✅" if st.session_state.layer_visibility.get(name, True) else "⬜"
                st.markdown(f'{visibility_icon} <span style="color:{color};">■</span> **{name.replace("_", " ").title()}**', unsafe_allow_html=True)
    
    except Exception as e:
        st.error(f"Error displaying map: {str(e)}")
        import traceback
        with st.expander("🔍 Error Details"):
            st.code(traceback.format_exc())


# Also update the "Clear All Data" button to reset map state:
# Replace the existing button code with:

if st.button("Clear All Data", use_container_width=True):
    st.session_state.geodataframes = {}
    st.session_state.dataframes = {}
    st.session_state.generated_code = []
    st.session_state.messages = []
    # Reset map state
    st.session_state.map_center = [39.8, -98.6]
    st.session_state.map_zoom = 6
    st.session_state.map_bounds = None
    st.session_state.layer_visibility = {}
    st.rerun()
