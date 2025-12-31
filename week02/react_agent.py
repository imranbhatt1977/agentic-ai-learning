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
    
KNOWLDGE_BASE = {
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
    
    TOOLS: Dict[str, Callable[[str], str]] = {
        "calculator": calsulator,
        "kb_lookuo": knowledge_base_lookup,
    }


#------------React Agent Core------------#

REACT_INSTRUCTIONS = """You are a helpful AI agent that used ReAct (Reason + Act).
You can use the following tools:
1. calculator[expression] - evaluate a math expression. e.g. calculator[2+3*4]
2. kb_lookup[query] - query a small knowledgr base, e.g. kb_lookup[what is an AI agent?]

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

def run_react_agent(user_query: str, max_steps:int = 5) -> str:
    """
    Main ReAct loop:
    - Ask LLM for next Thought/Action or Final Answer.
    - If Action is present, call the tool and append Observation.
    - Repeat until Final Answer.
    """
    
    history = REACT_INSTRUCTIONS + f"\n\nUser question: {user_query}\n"
    
    for step in range(max_steps):
        prompt = history + "\n\nUser question: {user_query}\n"
        
        llm_response = call_ollama_llm(prompt) 
        # Append model output to history
        history += llm_response + "\n"

        # print for visibility

        print(f"\n---LLM Step {step + 1} ---")
        print(llm_response)
        print("-------------------\n")

        # Check for Final Answer
        final_match = re.search(r"Final Answer:(.*)", llm_response, re.DOTALL)
        if final_match:
            return final_match.group(1).strip()
        # Look for a Action line
        action_line = None
        for line in llm_response.splitlines():
            if line.strip().startswith("Action:"):
                action_line = line.strip()
                break
        if not action_line:
        # if no action and no final answer, stop
            return "I could not determine an action or final answer."

        tool_name, argument = parse_action(action_line)
        if tool_name is None:
            return "I could not parse the action."
        
        tool = TOOLS.get(tool_name)
        if tool is None:
            observation = f"Unknown tool: {tool_name}"
        else:
            observation = tool(argument)

        # Add observation back into the history for the next LLM call.
        history += f"\nObservation: {observation}\n"

    return "I reached the maximum number of reasoning steps without a final answer."


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
    
