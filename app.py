import streamlit as st
import os
import asyncio
import json
from pathlib import Path
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import (
    HostExecutionPolicy,
    ShellToolMiddleware,
)
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langgraph.types import Command
import uuid
import tempfile

from deepagents_cli.skills.middleware import SkillsMiddleware
from deepagents_cli.config import settings

# Import mapping libraries
try:
    import geopandas as gpd
    import pandas as pd
    GEOPANDAS_AVAILABLE = True
except ImportError:
    GEOPANDAS_AVAILABLE = False

try:
    import folium
    from folium import plugins
    from streamlit_folium import st_folium
    FOLIUM_AVAILABLE = True
except ImportError:
    FOLIUM_AVAILABLE = False

# Set the wide layout of the web page
st.set_page_config(layout="wide", page_title="WEN-OKN")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "skills_loaded" not in st.session_state:
    st.session_state.skills_loaded = False
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []
if "geodataframes" not in st.session_state:
    st.session_state.geodataframes = {}
if "dataframes" not in st.session_state:
    st.session_state.dataframes = {}
if "generated_code" not in st.session_state:
    st.session_state.generated_code = []
if "skills_documentation" not in st.session_state:
    st.session_state.skills_documentation = {}
if "user_session_id" not in st.session_state:
    st.session_state.user_session_id = str(uuid.uuid4())[:8]
if "temp_dir" not in st.session_state:
    st.session_state.temp_dir = tempfile.mkdtemp(prefix=f"wenokn_{st.session_state.user_session_id}_")
if "current_view" not in st.session_state:
    st.session_state.current_view = "conversation"

# --- NEW: Initialize Map State ---
if "map_state" not in st.session_state:
    st.session_state.map_state = {
        "center": [39.8, -98.6],
        "zoom": 4,
        "last_active_layers": [], # Track user selection
        "known_layers": []       # Track which layers have already been processed
    }

def scan_skills_documentation():
    if st.session_state.skills_documentation:
        return st.session_state.skills_documentation
    current_directory = os.getcwd()
    skills_dir = Path(current_directory) / "skills"
    if not skills_dir.exists(): return {}
    skills_docs = {}
    for skill_dir in skills_dir.iterdir():
        if skill_dir.is_dir():
            skill_md = skill_dir / "SKILL.md"
            if skill_md.exists():
                try:
                    with open(skill_md, 'r', encoding='utf-8') as f:
                        content = f.read()
                        skills_docs[skill_dir.name] = {
                            'path': str(skill_md),
                            'content': content,
                            'short_desc': content.split('\n')[0] if content else "No description"
                        }
                except Exception as e:
                    st.warning(f"Could not read {skill_md}: {e}")
    st.session_state.skills_documentation = skills_docs
    return skills_docs

def get_llm():
    return ChatOpenAI(
        model="glm-4.6",
        base_url="https://ellm.nrp-nautilus.io/v1",
        api_key=os.environ.get("NRP_API_KEY"),
        temperature=0,
    )

def display_all_layers_map():
    if not st.session_state.geodataframes:
        st.info("No geographic data available yet. Start a conversation to generate maps!")
        return
    if not FOLIUM_AVAILABLE:
        st.error("⚠️ Folium not available.")
        return

    try:
        # 1. Identify new layers that haven't been 'fitted' yet
        current_layer_ids = list(st.session_state.geodataframes.keys())
        new_layer_ids = [l for l in current_layer_ids if l not in st.session_state.map_state["known_layers"]]
        
        # 2. Determine initial map view
        all_bounds = []
        for name, gdf in st.session_state.geodataframes.items():
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            all_bounds.append(gdf.total_bounds)

        # Logic: If there are NEW layers, fit the map to them. Otherwise, use saved state.
        if new_layer_ids and all_bounds:
            # Calculate bounds of all current data to zoom in
            min_x = min(b[0] for b in all_bounds)
            min_y = min(b[1] for b in all_bounds)
            max_x = max(b[2] for b in all_bounds)
            max_y = max(b[3] for b in all_bounds)
            
            initial_location = [(min_y + max_y) / 2, (min_x + max_x) / 2]
            initial_zoom = st.session_state.map_state["zoom"] # We'll let fit_bounds handle it
            should_fit = True
            # Update known layers so we don't force-fit again until next new data
            st.session_state.map_state["known_layers"] = current_layer_ids
        else:
            initial_location = st.session_state.map_state["center"]
            initial_zoom = st.session_state.map_state["zoom"]
            should_fit = False

        m = folium.Map(
            location=initial_location,
            zoom_start=initial_zoom,
            tiles=None,
            control_scale=True
        )

        # Basemap Options
        folium.TileLayer('OpenStreetMap', name='Street Map', overlay=False).add_to(m)
        folium.TileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 
                         attr='Esri', name='Satellite', overlay=False).add_to(m)
        folium.TileLayer('CartoDB positron', name='Light', overlay=False).add_to(m)

        colors = ['#4E79A7', '#F28E2B', '#E15759', '#76B7B2', '#59A14F', '#EDC948', '#B07AA1', '#FF9DA7', '#9C755F', '#BAB0AC']
        
        # 3. Add Layers
        for idx, (name, gdf) in enumerate(st.session_state.geodataframes.items()):
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                gdf = gdf.to_crs(epsg=4326)
            
            color = colors[idx % len(colors)]
            display_name = name.replace('_', ' ').title()
            
            # Logic: If it's a new layer, it's checked. If old, check against last_active_layers.
            # If last_active_layers is empty (first run), check everything.
            if name in new_layer_ids or not st.session_state.map_state["last_active_layers"]:
                show_layer = True
            else:
                show_layer = display_name in st.session_state.map_state["last_active_layers"]

            feature_group = folium.FeatureGroup(name=display_name, show=show_layer)
            
            def style_function(feature, color=color):
                return {'fillColor': color, 'color': color, 'weight': 1.5, 'fillOpacity': 0.4}
            
            tooltip_fields = [col for col in gdf.columns if col.lower() not in ['geometry', 'geom', 'the_geom', 'shape']]
            tooltip = folium.GeoJsonTooltip(fields=tooltip_fields, localize=True, sticky=False, labels=True,
                                            style="background-color: white; border: 1px solid black; font-size: 11px; max-height: 200px; overflow-y: auto;") if tooltip_fields else None
            
            folium.GeoJson(
                gdf,
                marker=folium.CircleMarker(radius=3, weight=1, fill=True, fill_opacity=0.7),
                style_function=style_function,
                tooltip=tooltip,
                name=display_name
            ).add_to(feature_group)
            
            feature_group.add_to(m)

        folium.LayerControl(position='topright', collapsed=False).add_to(m)
        plugins.Fullscreen(position='topleft').add_to(m)
        plugins.MousePosition().add_to(m)

        if should_fit and all_bounds:
            m.fit_bounds([[min_y, min_x], [max_y, max_x]], padding=[50, 50])

        # 4. Use returned_objects to capture state
        map_output = st_folium(
            m,
            width=None,
            height=600,
            use_container_width=True,
            returned_objects=["zoom", "center", "last_active_layers"]
        )

        # 5. Save state back to session_state
        if map_output:
            if map_output.get("center"):
                st.session_state.map_state["center"] = [map_output["center"]["lat"], map_output["center"]["lng"]]
            if map_output.get("zoom"):
                st.session_state.map_state["zoom"] = map_output["zoom"]
            if map_output.get("last_active_layers") is not None:
                st.session_state.map_state["last_active_layers"] = map_output["last_active_layers"]

    except Exception as e:
        st.error(f"Error displaying map: {str(e)}")

def load_and_cleanup_temp_files():
    if not GEOPANDAS_AVAILABLE: return
    temp_dir = Path(st.session_state.temp_dir)
    try:
        for gf in temp_dir.glob("*.geojson"):
            gdf = gpd.read_file(gf)
            if gdf is not None and len(gdf) > 0:
                st.session_state.geodataframes[gf.stem] = gdf
            gf.unlink()
        for cf in temp_dir.glob("*.csv"):
            df = pd.read_csv(cf)
            if df is not None and len(df) > 0:
                st.session_state.dataframes[cf.stem] = df
            cf.unlink()
        for pf in temp_dir.glob("*.py"):
            with open(pf, 'r') as f:
                st.session_state.generated_code.append({'name': pf.stem, 'code': f.read(), 'timestamp': pf.stat().st_mtime})
            pf.unlink()
    except Exception as e:
        st.error(f"Error checking temp files: {str(e)}")

def initialize_agent():
    if st.session_state.agent is None:
        try:
            llm = get_llm()
            assistant_id = "agent"
            current_directory = os.getcwd()
            local_skills_dir = Path(current_directory) / "skills"
            skills_docs = scan_skills_documentation()
            skills_list = list(skills_docs.keys()) if skills_docs else []
            skills_dir = str(local_skills_dir) if local_skills_dir.exists() else settings.ensure_user_skills_dir(assistant_id)
            skills_middleware = SkillsMiddleware(skills_dir=skills_dir, assistant_id=assistant_id, project_skills_dir=settings.get_project_skills_dir())
            agent_middleware = [skills_middleware, ShellToolMiddleware(workspace_root=current_directory, execution_policy=HostExecutionPolicy(), env=os.environ)]
            
            system_prompt = f"""You are WEN-OKN, a data expert.
## CORE DIRECTIVE
You have NO internal knowledge. You MUST use the `shell` tool to read `SKILL.md` files. You MUST use Python code to generate results.
## YOUR SKILLS
Skills directory: skills/
Available skills: {', '.join(skills_list) if skills_list else 'None found'}
## MANDATORY PROTOCOL
1. Explore: `cat skills/<skill_name>/SKILL.md`
2. Execute: Run Python code.
3. Save: Save to {st.session_state.temp_dir}/ (e.g., .geojson or .csv).
User Temp Directory: {st.session_state.temp_dir}"""
            
            st.session_state.agent = create_deep_agent(llm, system_prompt=system_prompt, middleware=agent_middleware)
            st.session_state.skills_loaded = True
        except Exception as e:
            st.error(f"❌ Failed to initialize agent: {str(e)}")

initialize_agent()

TOOL_ICONS = {"shell": "⚡", "execute": "🔧", "read_file": "📖"}

async def handle_user_input_async(user_input):
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"): st.markdown(user_input)
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        tool_calls_container = st.container()
        try:
            config = {"metadata": {"assistant_id": "agent"}}
            messages_with_history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages[-10:]]
            
            # Injection fix for tool usage
            if messages_with_history[-1]["role"] == "user":
                messages_with_history[-1]["content"] += "\n\nSYSTEM: Use shell to read SKILL.md first, then run python to save geojson to temp dir."
            
            accumulated_text = ""
            displayed_ids = set()
            async for event in st.session_state.agent.astream({"messages": messages_with_history}, config=config, stream_mode="messages"):
                if isinstance(event, tuple):
                    message = event[0]
                    if isinstance(message, AIMessage):
                        if message.content:
                            accumulated_text += message.content
                            response_placeholder.markdown(accumulated_text)
                        for tc in (message.tool_calls or []):
                            if tc['id'] not in displayed_ids:
                                displayed_ids.add(tc['id'])
                                with tool_calls_container: st.info(f"{TOOL_ICONS.get(tc['name'], '🔧')} Executing {tc['name']}")
                    elif isinstance(message, ToolMessage):
                        with tool_calls_container:
                            with st.expander(f"Output: {message.name}", expanded=False): st.code(message.content[:500])
            
            if accumulated_text:
                st.session_state.messages.append({"role": "assistant", "content": accumulated_text})
            load_and_cleanup_temp_files()
        except Exception as e:
            st.error(f"Error: {e}")

def handle_user_input(user_input):
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(handle_user_input_async(user_input))
    st.rerun()

# SIDEBAR
with st.sidebar:
    st.markdown("## 🌍 WEN-OKN")
    if st.button("Conversation", use_container_width=True, type="primary" if st.session_state.current_view == "conversation" else "secondary"):
        st.session_state.current_view = "conversation"
        st.rerun()
    if st.button("Map", use_container_width=True, type="primary" if st.session_state.current_view == "map" else "secondary"):
        st.session_state.current_view = "map"
        st.rerun()
    if st.button("Clear All Data", use_container_width=True):
        st.session_state.geodataframes = {}
        st.session_state.map_state["known_layers"] = []
        st.session_state.messages = []
        st.rerun()

# MAIN
if st.session_state.current_view == "conversation":
    st.markdown("### 💬 Chat")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    user_input = st.chat_input("Ask about rivers, plants, etc...")
    if user_input: handle_user_input(user_input)

elif st.session_state.current_view == "map":
    display_all_layers_map()
    with st.expander("📊 Layer Data"):
        for name, gdf in st.session_state.geodataframes.items():
            st.write(f"**{name}**")
            st.dataframe(gdf.drop(columns=['geometry'], errors='ignore'), height=150)
