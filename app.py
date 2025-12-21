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
from langgraph.checkpoint.memory import InMemorySaver

from deepagents_cli.skills.middleware import SkillsMiddleware
from deepagents_cli.config import settings

# Set the wide layout of the web page
st.set_page_config(layout="wide", page_title="WEN-OKN")

# Set up the title
st.markdown("### 🌍 WEN-OKN: Dive into Data, Never Easier")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "skills_loaded" not in st.session_state:
    st.session_state.skills_loaded = False
if "thread_id" not in st.session_state:
    st.session_state.thread_id = "streamlit_chat_001"

# Configuration section
with st.container():
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### ⚙️ Configuration")
    with col2:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1, key="temp_slider")

# Initialize LLM - removed cache to allow dynamic temperature updates
def get_llm():
    return ChatOpenAI(
        model="mimo-v2-flash",
        base_url="https://api.xiaomimimo.com/v1",
        api_key=st.secrets.get("XIAOMI_API_KEY", os.getenv("XIAOMI_API_KEY", "")),
        temperature=st.session_state.get("temp_slider", 0.3),
        top_p=0.95,
        streaming=True,  # Enable streaming for better UX
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

# Initialize agent with working skills middleware
def initialize_agent():
    if st.session_state.agent is None:
        try:
            llm = get_llm()
            
            # Setup directories
            assistant_id = "agent"
            current_directory = os.getcwd()
            local_skills_dir = Path(current_directory) / "skills"
            
            # Use local skills directory
            if local_skills_dir.exists():
                skills_dir = str(local_skills_dir)
                project_skills_dir = None
                st.info(f"✅ Loading skills from local directory: {skills_dir}")
            else:
                skills_dir = settings.ensure_user_skills_dir(assistant_id)
                project_skills_dir = settings.get_project_skills_dir()
                st.info(f"ℹ️ Loading skills from user directory: {skills_dir}")
            
            # Initialize skills middleware
            skills_middleware = SkillsMiddleware(
                skills_dir=skills_dir,
                assistant_id=assistant_id,
                project_skills_dir=project_skills_dir,
            )
            
            # Create middleware
            agent_middleware = [
                skills_middleware,
                ShellToolMiddleware(
                    workspace_root=current_directory,
                    execution_policy=HostExecutionPolicy(),
                    env=os.environ,
                ),
            ]
            
            # Improved system prompt
            system_prompt = """You are WEN-OKN, a geographic data assistant specializing in spatial analysis.

## CORE CAPABILITIES:
You have access to specialized geographic data skills that return GeoDataFrames:
- us_counties: US county boundaries
- us_states: US state boundaries
- power_plants: Power plant locations
- dams: Dam locations
- watersheds: Watershed boundaries
- rivers: River networks
- census_tracts: Census tract boundaries

## HOW TO RESPOND:

1. **For geographic queries**: 
   - Use the appropriate skill to fetch data
   - Filter/analyze the GeoDataFrame as needed
   - Create visualizations using streamlit
   - Explain your findings clearly

2. **For data exploration**:
   - Show relevant attributes and statistics
   - Create maps when appropriate
   - Provide context about the data

3. **Best Practices**:
   - Always confirm what data you're retrieving
   - Explain filtering/analysis steps
   - Present results visually when possible
   - Keep responses concise but informative

## EXAMPLE WORKFLOW:
User: "Find Ross county in Ohio"
Your approach:
1. "I'll retrieve US counties data and filter for Ross County in Ohio"
2. Use us_counties skill
3. Filter: counties[(counties['NAME'] == 'Ross') & (counties['STATE_NAME'] == 'Ohio')]
4. Display on map with st.map()
5. Explain what you found

Remember: Skills are tools - use them directly, don't overcomplicate!"""
            
            # Create the agent
            st.session_state.agent = create_deep_agent(
                llm,
                system_prompt=system_prompt,
                middleware=agent_middleware,
            )
            
            # Add checkpointer for conversation memory
            st.session_state.agent.checkpointer = InMemorySaver()
            
            # Store skills info
            st.session_state.skills_loaded = True
            st.session_state.skills_directory = skills_dir
            
            st.success("✅ Agent initialized successfully!")
            
        except Exception as e:
            st.error(f"❌ Failed to initialize agent: {str(e)}")
            st.exception(e)

# Initialize agent on first run
initialize_agent()

# Skills information section
if st.session_state.skills_loaded and "skills_directory" in st.session_state:
    with st.expander("📋 Available Skills", expanded=False):
        st.success(f"✅ Skills loaded from: {st.session_state.skills_directory}")
        
        st.markdown("**Geographic Skills:**")
        skills_list = [
            "🗺️ us_counties - USA counties",
            "🗺️ us_states - USA states", 
            "🏭 power_plants - Power plants",
            "🌊 dams - Dams",
            "💧 watersheds - Watersheds",
            "🌊 rivers - Rivers",
            "📊 census_tracts - Census tracts"
        ]
        
        cols = st.columns(2)
        for i, skill in enumerate(skills_list):
            with cols[i % 2]:
                st.markdown(f"• {skill}")
        
        st.markdown("**How to use:**")
        st.markdown("Just ask for what you want, e.g.:")
        st.markdown("- \"Find Ross county in Ohio\"")
        st.markdown("- \"Show power plants in California\"")
        st.markdown("- \"Display watersheds in Colorado\"")
        
elif not st.session_state.skills_loaded:
    st.info("🔄 Loading skills...")

# Tool icons for display
TOOL_ICONS = {
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "ls": "📁",
    "glob": "📁",
    "grep": "🔍",
    "shell": "⚡",
    "execute": "🔧",
    "web_search": "🌐",
    "http_request": "🌐",
    "task": "🤖",
    "write_todos": "📋",
    "us_counties": "🗺️",
    "us_states": "🗺️",
    "power_plants": "🏭",
    "dams": "🌊",
    "watersheds": "💧",
    "rivers": "🌊",
    "census_tracts": "📊",
}

def format_tool_display(tool_name: str, args: dict) -> str:
    """Format tool call for display."""
    if tool_name == "read_file":
        file_path = args.get("file_path", "unknown")
        return f"Reading: {file_path}"
    elif tool_name == "write_file":
        file_path = args.get("file_path", "unknown")
        return f"Writing: {file_path}"
    elif tool_name == "shell":
        command = args.get("command", "unknown")
        return f"Executing: {command}"
    elif tool_name == "ls":
        path = args.get("path", ".")
        return f"Listing: {path}"
    elif tool_name in ["us_counties", "us_states", "power_plants", "dams", "watersheds", "rivers", "census_tracts"]:
        return f"Fetching {tool_name.replace('_', ' ').title()} data"
    else:
        # Truncate args if too long
        args_str = str(args)
        if len(args_str) > 100:
            args_str = args_str[:97] + "..."
        return f"{tool_name}: {args_str}"

# Display chat messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Handle user input with improved streaming
async def handle_user_input_async(user_input):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get assistant response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        tool_calls_container = st.container()
        
        try:
            # Create config with thread_id for checkpointer
            config = {
                "configurable": {"thread_id": st.session_state.thread_id},
                "metadata": {"assistant_id": "agent"},
            }
            
            # Prepare input
            stream_input = {"messages": [{"role": "user", "content": user_input}]}
            
            accumulated_text = ""
            displayed_tool_ids = set()
            
            # Stream the response
            async for event in st.session_state.agent.astream(
                stream_input,
                config=config,
                stream_mode="messages",
            ):
                # Handle different event types
                if isinstance(event, tuple) and len(event) >= 2:
                    message, metadata = event[0], event[1] if len(event) > 1 else {}
                    
                    # Skip human messages
                    if isinstance(message, HumanMessage):
                        continue
                    
                    # Handle AI messages with content
                    if isinstance(message, AIMessage):
                        # Extract text content
                        if hasattr(message, 'content') and isinstance(message.content, str):
                            if message.content:
                                accumulated_text += message.content
                                response_placeholder.markdown(accumulated_text)
                        
                        # Handle tool calls
                        if hasattr(message, 'tool_calls') and message.tool_calls:
                            for tool_call in message.tool_calls:
                                tool_id = tool_call.get('id')
                                if tool_id and tool_id not in displayed_tool_ids:
                                    displayed_tool_ids.add(tool_id)
                                    tool_name = tool_call.get('name', 'unknown')
                                    tool_args = tool_call.get('args', {})
                                    icon = TOOL_ICONS.get(tool_name, "🔧")
                                    display_str = format_tool_display(tool_name, tool_args)
                                    
                                    with tool_calls_container:
                                        st.info(f"{icon} {display_str}")
                    
                    # Handle tool messages
                    elif isinstance(message, ToolMessage):
                        tool_name = getattr(message, "name", "")
                        tool_content = getattr(message, "content", "")
                        
                        # Show errors prominently
                        if isinstance(tool_content, str) and (
                            tool_content.lower().startswith("error") or
                            "failed" in tool_content.lower()
                        ):
                            with tool_calls_container:
                                st.error(f"❌ {tool_name}: {tool_content}")
            
            # Save final response
            if accumulated_text:
                st.session_state.messages.append({"role": "assistant", "content": accumulated_text})
            else:
                # If no text was accumulated, show a default message
                default_msg = "I've processed your request. The results should be displayed above."
                response_placeholder.markdown(default_msg)
                st.session_state.messages.append({"role": "assistant", "content": default_msg})
            
        except Exception as e:
            error_message = f"❌ An error occurred: {str(e)}"
            st.error(error_message)
            st.exception(e)
            st.session_state.messages.append({"role": "assistant", "content": error_message})

# Synchronous wrapper for async function
def handle_user_input(user_input):
    asyncio.run(handle_user_input_async(user_input))

# Main chat interface
st.markdown("## 💬 Chat Interface")

# Display existing messages
display_messages()

# Chat input
user_input = st.chat_input("Ask me about geographic data, counties, states, power plants, watersheds...")

if user_input:
    handle_user_input(user_input)
