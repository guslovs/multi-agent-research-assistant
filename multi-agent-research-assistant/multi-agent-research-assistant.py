from typing import Any
import asyncio
from agents import Agent, trace, Runner
from agents.tool import WebSearchTool
from dotenv import load_dotenv
import sqlite3
import uuid
import gradio as gr
from agent_instructions import agent_instructions

load_dotenv(override=True)

async def main():
    
    # creating a sql table to store conversation history
    conn = sqlite3.connect("research_assistants.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            session_id TEXT,
            agent_name TEXT,
            role TEXT,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()
    
    session_id = str(uuid.uuid4())
    
    # saving the conversation to database
    def save_to_database(session_id, agent_name, role, content):
        conn = sqlite3.connect("research_assistants.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (session_id, agent_name, role, content) VALUES (?, ?, ?, ?)", (session_id, agent_name, role, content))
        conn.commit()
        conn.close()
        
    # accessing conversation history
    def get_history(session_id):
        conn = sqlite3.connect("research_assistants.db")
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, agent_name, role, content
            FROM history
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "timestamp": ts,
                "agent_name": agent_name,
                "role": role,
                "content": content,
            }
            for (ts, agent_name, role, content) in rows
        ]
        
    history = get_history(session_id)
    
    search_agent = Agent[Any](
        name="Search Agent",
        instructions=agent_instructions[0]["instructions"],
        model="gpt-4o-mini",
        tools=[WebSearchTool()]
    )
    
    summary_agent = Agent[Any](
        name="Summary Agent",
        instructions=agent_instructions[1]["instructions"],
        model="gpt-4o-mini"
    )
    
    writer_agent = Agent[Any](
        name="Writer Agent",
        instructions=agent_instructions[2]["instructions"],
        model="gpt-4o-mini"
    )
    
    coordinator_agent = Agent[Any](
        name="Coordinator Agent",
        instructions=agent_instructions[3]["instructions"],
        model="gpt-4o-mini",
        tools=[
            search_agent.as_tool(tool_name="search_agent", tool_description="Search the web for information"),
            summary_agent.as_tool(tool_name="summary_agent", tool_description="Summarize the information"),
            writer_agent.as_tool(tool_name="writer_agent", tool_description="Write a report or article based on the summary")
        ]
    )
    
    fact_checker_agent = Agent[Any](
        name="Fact Checker Agent",
        instructions=agent_instructions[4]["instructions"],
        model="gpt-4o-mini"
    )
    
    citation_agent = Agent[Any](
        name="Citation Agent",
        instructions=agent_instructions[5]["instructions"],
        model="gpt-4o-mini"
    )
    
    critic_agent = Agent[Any](
        name="Critic Agent",
        instructions=agent_instructions[6]["instructions"],
        model="gpt-4o-mini"
    )
    
    main_agent = Agent[Any](
        name="Main Agent",
        instructions=agent_instructions[7]["instructions"],
        model="gpt-4o-mini",
        tools=[
            coordinator_agent.as_tool(tool_name="coordinator_agent", tool_description="Oversee the research workflow"),
            fact_checker_agent.as_tool(tool_name="fact_checker_agent", tool_description="Check the report for accuracy"),
            citation_agent.as_tool(tool_name="citation_agent", tool_description="Format the citations"),
            critic_agent.as_tool(tool_name="critic_agent", tool_description="Review the final report")
        ]
    )
    
    # user asks a question and gets an answer
    async def run_assistant(user_question):
        with trace("Multi-Agent Research Assistant"):
            result = await Runner.run(main_agent, user_question, context=history)
            save_to_database(session_id, "Main Agent", "User", user_question)
            return result.final_output
        
    # putting a async function into a sync function because gradio doesnt work with async functions
    def gradio_run(user_question):
        yield "Running..."
        answer = asyncio.run(run_assistant(user_question))
        yield answer
    
    # user interface
    with gr.Blocks(theme=gr.themes.Default(primary_hue="sky")) as ui:
        gr.Markdown("Multi Agent Research Assistant")
        query = gr.Textbox(label="What's your question?")
        btn = gr.Button("Run")
        answer = gr.Markdown(label="Answer")
        
        btn.click(fn=gradio_run, inputs=query, outputs=answer)
        query.submit(fn=gradio_run, inputs=query, outputs=answer)
    
    ui.launch(inbrowser=True)
            
asyncio.run(main())