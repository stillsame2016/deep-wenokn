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

llm = ChatOpenAI(
        model="mimo-v2-flash",
        base_url="https://api.xiaomimimo.com/v1",
        api_key=st.secrets["XIAOMI_API_KEY"],
        temperature=0.3,
        top_p=0.95,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "disabled"}
        }
    )

# Create the agent with custom tools and skills middleware
agent = create_deep_agent(
    llm,
    system_prompt="""    
    Use the skills to answer user questions accurately. When you need information
    that requires a tool, use it. Always provide clear and helpful responses.
    
    The read_file tool cannot access files outside the current working directory.

    ## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`

    **IMPORTANT - Path Handling:**
    - All file paths must be absolute paths (e.g., `/tmp/test/file.txt`)
    - Use the working directory from <env> to construct absolute paths
    - Example: To create a file in your working directory, use `/tmp/test/research_project/file.md`
    - Never use relative paths - always construct full absolute paths
    """
)

