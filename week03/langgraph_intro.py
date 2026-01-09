"""
week03/langgraph_intro.py

First LangGraph example:
- State with a list of messages.
- One LLM node using Ollama (your existing call_ollama_llm).
- One kb_lookup tool node.
- A simple router that decides whether to call the tool or answer directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal

from langgraph.graph import StateGraph, END

from week01.simple_llm import call_ollama_llm


# --- 1. Define the State -----------------------------------------------------


@dataclass
class ChatMessage:
    role: Literal["user", "assistant", "tool"]
    content: str


@dataclass
class AgentState:
    """
    The state that flows through the graph.

    For now:
    - messages: chat history (user / assistant / tool)
    - need_tool: whether we should call kb_lookup
    - summarize: whether the user is asking for a summary
    """
    messages: List[ChatMessage] = field(default_factory=list)
    need_tool: bool = False
    summarize: bool = False
    need_note: bool = False
    note_approved: bool = False
    pending_note: str = ""

# --- 2. A tiny kb_lookup tool (like Week 2, but simpler) ---------------------


KNOWLEDGE_BASE = {
    "ai agent": (
        "An AI agent is a system that perceives its environment, "
        "reasons about it, and takes actions to achieve goals."
    ),
    "langgraph": (
        "LangGraph lets you build LLM workflows as graphs with nodes, edges, "
        "and a shared state object."
    ),
}


def kb_lookup(query: str) -> str:
    q = query.lower()
    for key, value in KNOWLEDGE_BASE.items():
        if key in q:
            return value
    return (
        "I don't have an exact answer in my small knowledge base yet. "
        "Try asking about 'AI agent' or 'LangGraph'."
    )
import os

# Define where LangGraph notes will go

LANGGRAPH_NOTES_DIR = os.path.join("notes", "langgraph_notes")

def write_note_tool(content: str) -> str:
    """
    Appends content to a markdown file in the langgraph_notes folder.
    """
    os.makedirs(LANGGRAPH_NOTES_DIR, exist_ok=True)

    file_path = os.path.join(LANGGRAPH_NOTES_DIR, "session_notes.md")
    abs_path = os.path.abspath(file_path)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(content.strip() + "\n\n")

    return f"Note written to: {abs_path}"
# Helper for note generation

def generate_note_draft(text: str) -> str:
    prompt = (
        "Convert the following content into a concise, factual note.\n"
        "Rules:\n"
        "_ Use '_' hyphen bullets only (ASCII)\n"
        "_ No conversational tone\n"
        "_ 3-6 bullet points or a short paragraph\n\n"
        f"{text}\n\n\nNOTE:"
    )
    return call_ollama_llm(prompt).strip()

# --- 3. Define the nodes (functions) -----------------------------------------


def router_node(state: AgentState) -> AgentState:
    """
    Very simple router:
    - If user's last message mentions 'ai agent' or 'langgraph', we set need_tool = True.
    - If user's last message mentions 'summary' or 'summarize our conversation',
      set summarize = True.
    """
    if not state.messages:
        return state

    last_msg = state.messages[-1]
    if last_msg.role != "user":
        return state

    text = last_msg.content.lower()

    # Debug Print
    print(f"--- Router checking text: '{text}' ---")

    # Decide if we need the KB tool
    state.need_tool = ("ai agent" in text) or ("langgraph" in text)

    # Decide if we need to summarize
    state.summarize = ("summary" in text) or ("summarize" in text)

    #return state

    # Decide if we need to write notes
    state.need_note = any(word in text for word in ["note", "save", "record"])

    print(f"---Router set need_note to: {state.need_note} ---")

    return state


def tool_node(state: AgentState) -> AgentState:
    """
    If need_tool is True, call kb_lookup and append a tool message.
    """
    if not state.messages:
        return state

    last_msg = state.messages[-1]
    if last_msg.role != "user":
        return state

    if state.need_tool:
        tool_result = kb_lookup(last_msg.content)
        state.messages.append(ChatMessage(role="tool", content=tool_result))

    return state


def llm_node(state: AgentState) -> AgentState:
    """
    Call your local Ollama LLM using call_ollama_llm and append an assistant message.
    The prompt will include the conversation so far and any tool output.
    """
    conversation_lines = []
    for msg in state.messages:
        conversation_lines.append(f"{msg.role.upper()}: {msg.content}")

    prompt = (
        "You are a helpful assistant. You may see TOOL outputs in the conversation.\n"
        "Use them when helpful, and respond clearly to the user.\n\n"
        "Conversation so far:\n"
        + "\n".join(conversation_lines)
        + "\n\nASSISTANT:"
    )

    answer = call_ollama_llm(prompt)
    state.messages.append(ChatMessage(role="assistant", content=answer))
    return state

def summarize_node(state: AgentState) -> AgentState:
    """
    If summarize is True, generate a short summary of the conversation so far.
    """
    if not state.summarize:
        return state

    if not state.messages:
        return state

    # Turn messages into a text conversation
    convo_lines = [f"{m.role.upper()}: {m.content}" for m in state.messages]
    convo_text = "\n".join(convo_lines)

    prompt = (
        "You are a helpful assistant. Here is a conversation between a user and an assistant "
        "(and possibly tools). Please provide a short, clear summary of the key points.\n\n"
        f"{convo_text}\n\n"
        "Summary:"
    )

    summary = call_ollama_llm(prompt)

    # Append the summary as an assistant message
    state.messages.append(
        ChatMessage(role="assistant", content=f"(Summary) {summary}")
    )

    # Optionally reset summarize so we don't summarize repeatedly
    state.summarize = False

    return state

# ---5. Create review_node ------------------

def review_node(state: AgentState) -> AgentState:
    """
    security layer: Asks the use to approve the note content.
    """

    if not state.need_note:
        return state
    
    assistant_msgs = [m for m in state.messages if m.role == "assistant"]
    if not assistant_msgs:
        return state
    content = assistant_msgs[-1].content
    note_draft = generate_note_draft(content)
    state.pending_note = note_draft

    print("\n--- SECURITY REVIEW: PENDING NOTE ---")
    print(state.pending_note)
    print("------------------------------------")

    user_choice = input("Do you approve saving this note? (yes/no): ").strip().lower()

    if user_choice == "yes":
        state.note_approved = True
        print(">>> Access Granted. Proceeding to save....")
    else:
        state.pending_note = ""
        state.note_approved = False
        state.need_note = False
        print(">>> Access Denied. Note will not be saved.")
        state.messages.append(ChatMessage(role="assistant", content="Note save cancelled by user."))
    return state

# ---6. Create the note_node function ------------------------------------------------------

def note_node(state: AgentState) -> AgentState:
    if not state.need_note or not state.note_approved:
        return state

    if state.pending_note.strip():
        result = write_note_tool(state.pending_note)
        state.messages.append(ChatMessage(role="tool", content=result))
        state.messages.append(ChatMessage(role="assistant", content="Note saved (approved)."))
    else:
        state.messages.append(ChatMessage(role="assistant", content="No note content to save."))

    state.need_note = False
    state.note_approved = False
    state.pending_note = ""
    return state


# --- 6. Build the graph ------------------------------------------------------

def router_logic(state: AgentState) -> Literal["tools", "llm", "review"]:
    """
    This function decides the NEXT node to visit.
    """

    if state.need_tool:
        return "tools"
    if state.need_note:
        return "review"
    return "llm"

def build_graph():
    """
    Graph structure:

        (start) -> router_node
            |
            v
        tool_node
            |
            v
        llm_node -> END

    One pass per user query.
    """
    graph = StateGraph(AgentState)

    # Add the nodes
    graph.add_node("router", router_node)
    graph.add_node("tools", tool_node)
    graph.add_node("llm", llm_node)
    graph.add_node("review", review_node)
    graph.add_node("note", note_node)
    graph.add_node("summarize", summarize_node)

    graph.set_entry_point("router")

    #--- NEW: Conditional Routing ---
    # After 'router', call 'router_logic' to decide where to go next
    graph.add_conditional_edges(
        "router",
        router_logic,
        {
            "tools": "tools",
            "llm": "llm",
            "review": "review"
        }
    )


    # Edges
    graph.add_edge("tools", "llm")
    graph.add_edge("llm", "review")
    graph.add_edge("review", "note")
    graph.add_edge("note", "summarize")
    graph.add_edge("summarize", END)

    return graph.compile()


# --- 7. Simple CLI loop ------------------------------------------------------

def interactive_loop():
    app = build_graph()

    print("=== Week 3: LangGraph Intro (with running history) ===")
    print("Ask a question (type 'exit' to quit).\n")

    # This will persist across turns
    full_history: List[ChatMessage] = []

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        # Add the new user message to a copy of history for this run
        current_messages = full_history + [ChatMessage(role="user", content=user_input)]

        # Build state with all messages so far
        state = AgentState(messages=current_messages)

        # Run the graph once – LangGraph returns a dict-like state
        final_state = app.invoke(state)

        # final_state is a dict, so access ["messages"]
        messages = final_state.get("messages", [])

        # Extract assistant messages from this run
        assistant_msgs = [m for m in messages if m.role == "assistant"]

        if assistant_msgs:
            # Show only the last assistant message (could be the summary)
            reply = assistant_msgs[-1].content
            print(f"\nAssistant: {reply}\n")

            # Update full_history:
            #  - we already had history + user
            #  - now we append this final assistant reply
            full_history.append(ChatMessage(role="user", content=user_input))
            full_history.append(assistant_msgs[-1])
        else:
            print("\nAssistant: (No assistant reply generated.)\n")
            # Still store the user turn so it's visible next time
            full_history.append(ChatMessage(role="user", content=user_input))

if __name__ == "__main__":
    interactive_loop()
