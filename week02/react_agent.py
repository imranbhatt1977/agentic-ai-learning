import re
from typing import Dict, Callable

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'week01'))
from simple_llm import call_ollama_llm


#------------Tools------------#

def calculator(expression: str) -> str:
    """A simple calculator tool that evaluates basic arithmetic expressions. Example: "2+3*4"""
    try:
        # WARNING: Using eval can be dangerous. In production, use a proper math parser.
        result = eval(expression, {"__builtins__": {}})
        return str(result)
    except Exception as e:
        return f"Error in calculation: {e}"
    
KNOWLEDGE_BASE = {
    "ai agent": "An AI agent is a system that perceives its environment, "
                "reasons about it, and takes actions to achieve goals.",
    "react pattern": "ReAct (Reason + Act) is a prompting pattern where the model "
                     "interleaves reasoning steps (Thought) with tool use (Action) "
                     "and observations before giving a Final Answer.",
    "langgraph": "LangGraph is a framework built on top of LangChain that lets you "
                 "define LLM workflows as graphs with state, nodes, and edges."
}

def knowledge_base_lookup(query: str) -> str:
    """A simple lookup in a small in-memory knowledge base."""
    q = query.lower().strip()
    for key, value in KNOWLEDGE_BASE.items():
        if key in q:
            return value
        return(
            "I don't have an exact answer in my small knowledge base yet."
            "Try asking about 'AI agent', 'ReAct pattern', or 'Langgraph'."
        )
    
NOTES_DIR = "notes/react_notes"


def write_note(argument: str) -> str:
    """
    Write a note to a markdown file.

    Expected argument format:
        title | content
    """
    print("DEBUG: write_note TOOL CALLED with argument:", repr(argument))

    os.makedirs(NOTES_DIR, exist_ok=True)

    if "|" in argument:
        title_part, content_part = argument.split("|", 1)
        title = title_part.strip()
        content = content_part.strip()
    else:
        title = "untitled"
        content = argument.strip()

    safe_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).rstrip()
    if not safe_title:
        safe_title = "untitled"
    filename = safe_title.lower().replace(" ", "_") + ".md"

    path = os.path.join(NOTES_DIR, filename)

    print("DEBUG: Attempting to save file to:", os.path.abspath(path))

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# {title}\n\n")
        f.write(content)

    return f"Note saved to {path}"
    
TOOLS: Dict[str, Callable[[str], str]] = {
    "calculator": calculator,
    "kb_lookup": knowledge_base_lookup,
    "write_note": write_note,
    }


#------------React Agent Core------------#

REACT_INSTRUCTIONS = """You are a helpful AI agent that used ReAct (Reason + Act).
You can use the following tools:
1. calculator[expression] - evaluate a math expression. e.g. calculator[2+3*4]
2. kb_lookup[query] - query a small knowledge base, e.g. kb_lookup[what is an AI agent?]
3. write_note[title | content] - write a markdown note file. Example:
   write_note[AI Agents | AI agents are systems that perceive their environment...]

You MUST follow this format exactly:

Thought: your reasoning here
Action: tool_name[argument]
Observation: result of the tool call

You can repeat Thought/Action/Observation several times.
When you are ready to answer the user, output:

Final Answer: your final answer here

DO NOT skip 'Final Answer:'.
"""

def parse_action(line:str):
    """
    Parse an action line like: Action: calculator[2+3]
    Returns (tool_name, argument) or (None, None) if it doesn't match.
    """
    match = re.match(r"Action:\s*([a-zA-Z_]+)\[(.*)\]\s*$", line)
    if not match:
        return None, None
    tool_name = match.group(1).strip()
    argument = match.group(2).strip()
    return tool_name, argument

def run_react_agent(user_query: str, max_steps: int = 5) -> str:
    """
    Main ReAct loop:
    - Ask LLM for next Thought/Action or Final Answer.
    - If Action is present, call the tool and append a real Observation.
    - Repeat until Final Answer or max_steps or write_note_calls limit.
    """
    print("DEBUG: run_react_agent version WITH cut-off logic is running")

    history = REACT_INSTRUCTIONS + f"\n\nUser question: {user_query}\n"

    write_note_calls = 0
    MAX_WRITE_NOTE_CALLS = 3  # after this, we stop and return a final answer

    for step in range(max_steps):
        # If we've already written the note enough times, stop here
        if write_note_calls >= MAX_WRITE_NOTE_CALLS:
            return (
                "I've created and updated your note several times. "
                "You can read it in 'notes/react_notes/ai_agents.md'."
            )

        prompt = history + "\nPlease continue the reasoning.\n"
        llm_response = call_ollama_llm(prompt)

        print(f"\n--- LLM Step {step + 1} ---")
        print(llm_response)
        print("-------------------------\n")

        lines = llm_response.splitlines()

        # 1) FIRST: look for an Action line
        action_line = None
        action_line_index = -1
        for i, line in enumerate(lines):
            if line.strip().startswith("Action:"):
                action_line = line.strip()
                action_line_index = i
                break

        if action_line:
            # We have an Action → run the tool, ignore any Final Answer in this step
            tool_name, argument = parse_action(action_line)
            if tool_name is None:
                history += llm_response + "\n"
                return (
                    "I finished most of the work, but the last action was malformed. "
                    "Your note should still be saved."
                )

            print(f"DEBUG: About to call tool '{tool_name}' with argument: {argument!r}")
            tool = TOOLS.get(tool_name)
            if tool is None:
                observation = f"Unknown tool: {tool_name}"
            else:
                observation = tool(argument)
                if tool_name == "write_note":
                    write_note_calls += 1
            print("DEBUG: Tool returned observation:", observation)

            # Keep only up to the Action line, then append OUR observation
            llm_response_up_to_action = "\n".join(lines[:action_line_index + 1])
            history += llm_response_up_to_action + "\n"
            history += f"Observation: {observation}\n"

            continue

        # 2) If there was NO Action line, THEN check for Final Answer
        final_match = re.search(r"Final Answer:(.*)", llm_response, re.DOTALL)
        if final_match:
            final_text = final_match.group(1).strip()
            if not final_text:
                # Empty final answer → still give something useful
                return (
                    "I've created a note about AI agents. "
                    "You can read it in 'notes/react_notes/ai_agents.md'."
                )
            return final_text

        # 3) No action, no final answer → stop gracefully
        history += llm_response + "\n"
        return (
            "I've done most of the work, but couldn't interpret the last step. "
            "Your note should be in 'notes/react_notes/ai_agents.md'."
        )

    # If we exit the loop by hitting max_steps
    return (
        "I've reached my reasoning step limit. "
        "Your note should be saved in 'notes/react_notes/ai_agents.md'."
    )


def interactive_loop():
    print("=== ReAct Agent (Ollama) ===")
    print("Tools: calculator, kb_lookup")
    print("Type 'exit' to quit.\n")

    while True:
        query = input("You: ").strip()
        if query.lower() in {"exit", "quit"}:
            print("Goodbaye!")
            break
        if not query:
            continue
            
        answer = run_react_agent(query)
        print(f"\nFinal Answer: {answer}\n")

if __name__ == "__main__":
    interactive_loop()
    
