import json
import urllib.request
import urllib.error


def call_ollama_llm(prompt: str, model: str = "llama3") -> str:
    """
    Calls the Ollama API directly via HTTP.
    """
    url = "http://localhost:11434/api/generate"
    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,  # get full response
    }

    jsondata = json.dumps(data).encode("utf-8")

    # NOTE: use headers=..., not content_type=
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=jsondata, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("response", "")
    except urllib.error.URLError as e:
        return f"Error: Could not connect to Ollama. Is it running? ({e})"
    except Exception as e:
        return f"Error: {e}"

def chat_loop():
    system_prompt = (
        "You are a friendly, concise Python and AI tutor. "
        "Explain things clearly and use examples when helpful."
    )

    print("--- Simple LLM Chat (Ollama API) ---")
    print("Type 'exit' to quit.\n")

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not user_input:
            continue

        full_prompt = f"{system_prompt}\n\nUser: {user_input}\nAssistant:"
        
        print("\nThinking...")
        response = call_ollama_llm(full_prompt)
        print(f"LLM: {response}\n")

if __name__ == "__main__":
    chat_loop()