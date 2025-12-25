import json
import os
from datetime import datetime
from typing import List, Dict

from simple_llm import call_ollama_llm  # reuse your wrapper


HISTORY_FILE = "notes/study_buddy_history.json"


def load_history() -> List[Dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


def save_history(history: List[Dict]) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def summarize_session(history: List[Dict]) -> str:
    if not history:
        return "No history yet. Ask some questions first."

    # Use the last 10 turns for a concise summary
    convo_text = ""
    for turn in history[-10:]:
        convo_text += f"User: {turn['user']}\nAssistant: {turn['assistant']}\n\n"

    prompt = (
        "You are a study summary assistant. I will give you a recent conversation "
        "between a learner and an AI tutor. Summarize what the learner asked and "
        "what key concepts were explained. Provide a concise bullet-point summary.\n\n"
        f"Conversation:\n{convo_text}\n\nSummary:"
    )

    return call_ollama_llm(prompt)


def study_buddy_loop(goal: str):
    print("=== Study Buddy (Ollama) ===")
    print("Commands: /summary (summarize), /exit (quit)")
    print(f"Your current learning goal: {goal}\n")

    history = load_history()

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() in {"/exit", "exit", "quit"}:
            print("Goodbye! Your session history is saved.")
            save_history(history)
            break

        if user_input.lower() in {"/summary", "summary"}:
            print("\n[Generating session summary...]\n")
            summary = summarize_session(history)
            print(summary + "\n")
            continue

        # Short-term memory: last few turns
        recent_turns = history[-5:]
        context_text = ""
        for turn in recent_turns:
            context_text += f"User: {turn['user']}\nAssistant: {turn['assistant']}\n"

        system_prompt = (
            "You are a helpful AI tutor helping the user learn Agentic AI and related topics. "
            "Use the conversation context and their stated goal to give clear, concise answers."
        )

        full_prompt = (
            f"{system_prompt}\n\n"
            f"User's goal: {goal}\n\n"
            f"Recent conversation:\n{context_text}\n\n"
            f"Now the user asks: {user_input}\n\n"
            f"Assistant:"
        )

        print("\nThinking...")
        assistant_reply = call_ollama_llm(full_prompt)
        print(f"Tutor: {assistant_reply}\n")

        history.append(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "user": user_input,
                "assistant": assistant_reply,
            }
        )

        # Autosave every 5 turns
        if len(history) % 5 == 0:
            save_history(history)


if __name__ == "__main__":
    print("Welcome to your Study Buddy.")
    learning_goal = input(
        "What is your current learning goal? (e.g., 'Learn agentic AI in 3 months'): "
    ).strip()
    if not learning_goal:
        learning_goal = "Learn agentic AI in 3 months"
    study_buddy_loop(learning_goal)