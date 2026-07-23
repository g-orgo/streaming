from PyStreamingTool.llm.core import LlamaChat
from PyStreamingTool.api.api import app
from fastapi.testclient import TestClient
from httpx2 import Response

test_client = TestClient(app)


def test_chat_generation() -> None:
    """ 
        Valida que a LLM está operacional e que não
        há nenhum problema com o modelo
    """
    chat = LlamaChat()
    user_input = "Qual a capital de Rio Grande do Sul no Brasil?"
    expect_output = "Porto Alegre"
    llm_response = chat.get_response({"role": "user", "content": user_input})
    
    assert llm_response is not None
    assert expect_output in llm_response

def test_api() -> None:
    """
        Valida que a API está conseguindo
        efetivamente enviar mensagens para a LLM
    """
    
    api_response: Response = test_client.post(url="/api/v1/chat", json={"user_input": "Qual a capital do Rio Grande do Sul no sul do Brasil?"})
    expect_output = "Porto Alegre"
    
    assert api_response is not None
    assert expect_output in api_response.text