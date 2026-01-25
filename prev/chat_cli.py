from __future__ import annotations

from core.state import ChatState
from core.text import bidi_fix
from core.assistant import handle_message

def main():
    print("🟢 Live Chat (type 'exit' to quit)")
    print("Commands: /reset\n")

    state = ChatState()

    while True:
        msg = input("You: ").strip()
        if not msg:
            continue
        if msg.lower() in {"exit", "quit"}:
            break

        reply = handle_message(msg, state)
        print("Bot:", bidi_fix(reply or "…"))
        print()

if __name__ == "__main__":
    main()
