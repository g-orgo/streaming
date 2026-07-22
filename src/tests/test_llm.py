from PyStreamingTool.llm.core import LlamaChat

def test_chat_generation() -> None:
    chat = LlamaChat()
    user_input = "Qual a capital de Rio Grande do Sul no Brasil?"
    expect_output = "Porto Alegre"
    response = chat.get_response([{"role": "user", "content": user_input}])
    assert response is not None
    assert expect_output in response