from react_agent import write_note, NOTES_DIR
import os

if __name__ == "__main__":
    arg = "AI Agents Overview | AI agents are systems that perceive their environment and act to achieve goals."
    result = write_note(arg)
    print("Tool returned:", result)
    print("NOTES_DIR:", os.path.abspath(NOTES_DIR))