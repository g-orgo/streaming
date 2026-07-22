from PyStreamingTool.llm.core import LlamaChat


def main():
    print("Llama LLM Chat - Type 'exit' to quit.")

    chat = LlamaChat()
    messages = []

    while True:
        user_input = input("\nYou: ")

        if user_input.lower() in ["exit", "quit"]:
            print("\nExiting. Goodbye!")
            break

        messages.append(chat.get_response([{"role": "user", "content": user_input}])) # type: ignore
        print(f"Llama: {messages[-1]}")


if __name__ == "__main__":
    main()
