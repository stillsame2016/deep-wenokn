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
from langchain_core.messages import HumanMessage, ToolMessage
from langgraph.types import Command, Interrupt
from langgraph.checkpoint.memory import InMemorySaver

from deepagents_cli.skills.middleware import SkillsMiddleware
from deepagents_cli.config import settings

# Set the wide layout of the web page
st.set_page_config(layout="wide", page_title="WEN-OKN")

# Set up the title
st.markdown("### &nbsp; WEN-OKN: Dive into Data, Never Easier")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "skills_loaded" not in st.session_state:
    st.session_state.skills_loaded = False

# Configuration section (moved to main area)
with st.container():
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### Configuration")
    with col2:
        temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.1, key="temp_slider")

# Initialize LLM
@st.cache_resource
def get_llm():
    return ChatOpenAI(
        model="mimo-v2-flash",
        base_url="https://api.xiaomimimo.com/v1",
        api_key=st.secrets["XIAOMI_API_KEY"],
        temperature=st.session_state.get("temp_slider", 0.3),
        top_p=0.95,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

# Initialize agent without complex skills middleware
def initialize_agent():
    if st.session_state.agent is None:
        llm = get_llm()
        
        current_directory = os.getcwd()
        
        # Simple middleware without skills complexity
        agent_middleware = [
            ShellToolMiddleware(
                workspace_root=current_directory,
                execution_policy=HostExecutionPolicy(),
                env=os.environ,
            ),
        ]
        
        # Simple, direct system prompt
        system_prompt = """
        You are WEN-OKN, a helpful AI assistant for geographic data analysis.
        
        ## YOUR CAPABILITIES:
        You can help with geographic data using Python libraries. When users ask for geographic information:
        
        ## HOW TO HANDLE GEOGRAPHIC REQUESTS:
        
        For requests like "Find Ross county in Ohio":
        1. Use Python with geopandas to get the data
        2. Use available Python libraries in the environment
        3. Create a simple script to fetch and display the data
        4. ALWAYS display the result as a map using st.map()
        5. Provide explanation of what's shown
        
        ## EXAMPLE APPROACH:
        ```python
        import geopandas as gpd
        import streamlit as st
        
        # Get counties data (use available datasets)
        # Filter for Ross County, Ohio
        # Display with st.map()
        ```
        
        ## IMPORTANT:
        - Keep scripts simple and focused
        - Always show maps for geographic data
        - Use shell tool to run Python scripts
        - Write scripts to /tmp/ and execute them
        - Don't try to access restricted directories
        
        Be helpful and create visual geographic responses!
        """
        
        # Create the agent with simple middleware
        st.session_state.agent = create_deep_agent(
            llm,
            system_prompt=system_prompt,
            middleware=agent_middleware,
        )
        
        # Add checkpointer
        st.session_state.agent.checkpointer = InMemorySaver()
        
        # Store skills info for reference
        st.session_state.skills_loaded = True
        st.session_state.skills_directory = "Using direct Python approach"

# Initialize agent
initialize_agent()

# Skills information section
if st.session_state.skills_loaded and "skills_directory" in st.session_state:
    with st.expander("📋 System Information", expanded=False):
        st.success(f"✅ {st.session_state.skills_directory}")
        st.markdown("**Available Capabilities:**")
        st.markdown("- 🗺️ Geographic data analysis with Python")
        st.markdown("- 📊 Map visualization using Streamlit")
        st.markdown("- 🔍 Data filtering and analysis")
        st.markdown("- 📈 Interactive geographic displays")
        st.markdown("**Libraries Available:**")
        st.markdown("- geopandas, pandas, streamlit")
        st.markdown("- shapely, matplotlib, plotly")
elif not st.session_state.skills_loaded:
    st.info("🔄 Initializing system...")

# Display chat messages
def display_messages():
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "assistant":
                st.markdown(message["content"])
            else:
                st.markdown(message["content"])

# Tool icons for display
TOOL_ICONS = {
    "read_file": "📖",
    "write_file": "✏️",
    "edit_file": "✂️",
    "ls": "📁",
    "glob": "🔍",
    "grep": "🔎",
    "shell": "⚡",
    "execute": "🔧",
    "web_search": "🌐",
    "http_request": "🌍",
    "task": "🤖",
    "write_todos": "📋",
}

def format_tool_display(tool_name: str, args: dict) -> str:
    """Format tool call for display."""
    if tool_name == "read_file":
        file_path = args.get("file_path", "unknown")
        return f"Read file: {file_path}"
    elif tool_name == "write_file":
        file_path = args.get("file_path", "unknown")
        content_preview = args.get("content", "")[:50]
        return f"Write file: {file_path} ({content_preview}...)"
    elif tool_name == "shell":
        command = args.get("command", "unknown")
        return f"Shell: {command}"
    elif tool_name == "ls":
        path = args.get("path", "unknown")
        return f"List directory: {path}"
    elif tool_name == "write_todos":
        todos = args.get("todos", [])
        return f"Update todos ({len(todos)} items)"
    else:
        return f"{tool_name}: {args}"

# Handle user input with detailed execution
async def handle_user_input_detailed(user_input):
    # Add user message to chat
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Get assistant response with detailed execution
    with st.chat_message("assistant"):
        # Create a placeholder for streaming content
        response_placeholder = st.empty()
        tool_calls_container = st.container()
        
        try:
            # Create config with thread_id for checkpointer
            config = {
                "configurable": {"thread_id": "streamlit_chat"},
                "metadata": {"assistant_id": "agent"},
            }
            
            stream_input = {"messages": [{"role": "user", "content": user_input}]}
            
            has_responded = False
            pending_text = ""
            tool_call_buffers = {}
            displayed_tool_ids = set()
            tool_calls_html = ""
            
            while True:
                interrupt_occurred = False
                hitl_response = {}
                pending_interrupts = {}
                
                async for chunk in st.session_state.agent.astream(
                    stream_input,
                    stream_mode=["messages", "updates"],
                    subgraphs=True,
                    config=config,
                    durability="exit",
                ):
                    if not isinstance(chunk, tuple) or len(chunk) != 3:
                        continue
                    
                    _namespace, current_stream_mode, data = chunk
                    
                    # Handle UPDATES stream - for interrupts and todos
                    if current_stream_mode == "updates":
                        if isinstance(data, dict):
                            # Check for interrupts
                            if "__interrupt__" in data:
                                interrupts = data["__interrupt__"]
                                if interrupts:
                                    for interrupt_obj in interrupts:
                                        pending_interrupts[interrupt_obj.id] = interrupt_obj.value
                                        interrupt_occurred = True
                            
                            # Check for todo updates
                            chunk_data = next(iter(data.values())) if data else None
                            if chunk_data and isinstance(chunk_data, dict) and "todos" in chunk_data:
                                new_todos = chunk_data["todos"]
                                with tool_calls_container:
                                    st.markdown("### 📋 Todo List Updated:")
                                    for i, todo in enumerate(new_todos, 1):
                                        status_icon = "✅" if todo["status"] == "completed" else "🔄" if todo["status"] == "in_progress" else "⏳"
                                        st.markdown(f"  {i}. {status_icon} {todo['content']}")
                    
                    # Handle MESSAGES stream - for content and tool calls
                    elif current_stream_mode == "messages":
                        if not isinstance(data, tuple) or len(data) != 2:
                            continue
                        
                        message, _metadata = data
                        
                        if isinstance(message, HumanMessage):
                            continue
                        
                        if isinstance(message, ToolMessage):
                            # Show tool results
                            tool_name = getattr(message, "name", "")
                            tool_content = getattr(message, "content", "")
                            tool_status = getattr(message, "status", "success")
                            
                            if tool_name == "shell" and tool_status != "success":
                                with tool_calls_container:
                                    st.error(f"❌ Shell command failed: {tool_content}")
                            elif tool_content and isinstance(tool_content, str):
                                stripped = tool_content.lstrip()
                                if stripped.lower().startswith("error"):
                                    with tool_calls_container:
                                        st.error(f"❌ Tool error: {tool_content}")
                            
                            continue
                        
                        # Check if this is an AIMessageChunk
                        if not hasattr(message, "content_blocks"):
                            continue
                        
                        # Process content blocks
                        for block in message.content_blocks:
                            block_type = block.get("type")
                            
                            # Handle text blocks
                            if block_type == "text":
                                text = block.get("text", "")
                                if text:
                                    if not has_responded:
                                        has_responded = True
                                    pending_text += text
                                    # Update the placeholder with new text
                                    response_placeholder.markdown(pending_text)
                            
                            # Handle tool call chunks
                            elif block_type in ("tool_call_chunk", "tool_call"):
                                chunk_name = block.get("name")
                                chunk_args = block.get("args")
                                chunk_id = block.get("id")
                                chunk_index = block.get("index")
                                
                                # Use index as stable buffer key; fall back to id if needed
                                buffer_key = chunk_index if chunk_index is not None else chunk_id if chunk_id is not None else f"unknown-{len(tool_call_buffers)}"
                                
                                buffer = tool_call_buffers.setdefault(
                                    buffer_key,
                                    {"name": None, "id": None, "args": None, "args_parts": []},
                                )
                                
                                if chunk_name:
                                    buffer["name"] = chunk_name
                                if chunk_id:
                                    buffer["id"] = chunk_id
                                
                                if isinstance(chunk_args, dict):
                                    buffer["args"] = chunk_args
                                    buffer["args_parts"] = []
                                elif isinstance(chunk_args, str):
                                    if chunk_args:
                                        parts = buffer.setdefault("args_parts", [])
                                        if not parts or chunk_args != parts[-1]:
                                            parts.append(chunk_args)
                                        buffer["args"] = "".join(parts)
                                elif chunk_args is not None:
                                    buffer["args"] = chunk_args
                                
                                buffer_name = buffer.get("name")
                                buffer_id = buffer.get("id")
                                if buffer_name is None:
                                    continue
                                
                                parsed_args = buffer.get("args")
                                if isinstance(parsed_args, str):
                                    if not parsed_args:
                                        continue
                                    try:
                                        parsed_args = json.loads(parsed_args)
                                    except json.JSONDecodeError:
                                        continue
                                elif parsed_args is None:
                                    continue
                                
                                # Ensure args are in dict form
                                if not isinstance(parsed_args, dict):
                                    parsed_args = {"value": parsed_args}
                                
                                # Display the tool call
                                if buffer_id is not None and buffer_id not in displayed_tool_ids:
                                    displayed_tool_ids.add(buffer_id)
                                    icon = TOOL_ICONS.get(buffer_name, "🔧")
                                    display_str = format_tool_display(buffer_name, parsed_args)
                                    
                                    with tool_calls_container:
                                        st.markdown(f"  {icon} {display_str}")
                                
                                tool_call_buffers.pop(buffer_key, None)
                        
                        if getattr(message, "chunk_position", None) == "last":
                            if pending_text:
                                pending_text = ""
                
                # Handle interrupts if they occurred
                if interrupt_occurred:
                    # Auto-approve all tool actions for Streamlit
                    for interrupt_id, hitl_request in pending_interrupts.items():
                        decisions = []
                        for action_request in hitl_request["action_requests"]:
                            description = action_request.get("description", "tool action")
                            with tool_calls_container:
                                st.info(f"⚡ Auto-approving: {description}")
                            decisions.append({"type": "approve"})
                        hitl_response[interrupt_id] = {"decisions": decisions}
                    
                    # Resume the agent with the human decision
                    stream_input = Command(resume=hitl_response)
                    continue
                else:
                    break
            
            # Add final response to message history
            if pending_text:
                st.session_state.messages.append({"role": "assistant", "content": pending_text})
            
        except Exception as e:
            error_message = f"An error occurred: {str(e)}"
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})

# Handle user input (wrapper for async function)
def handle_user_input(user_input):
    # Run the async function
    asyncio.run(handle_user_input_detailed(user_input))

# Main chat interface
st.markdown("## Chat Interface")

# Display existing messages
display_messages()

# Chat input
user_input = st.chat_input("Ask me anything about data analysis, geographic information, or research...")

if user_input:
    handle_user_input(user_input)
