# Guia pratico: legendas simultaneas e gravacao recente no Windows

## 1. Resultado esperado

Ao final, voce tera um aplicativo Windows em Python que:

- escuta o microfone e o audio reproduzido pelo computador;
- transcreve fala continuamente;
- traduz ingles para o idioma configurado e outros idiomas para ingles;
- mostra legendas em um overlay sempre no topo e opcionalmente click-through;
- mantem historico pesquisavel com timestamps;
- oferece configuracoes de dispositivos, idiomas, modelos e atalhos;
- conserva uma janela recente de tela e audio com baixo impacto;
- ao pressionar um atalho global, salva os segundos anteriores em MP4;
- continua responsivo sob falha de dispositivo, modelo ou provider.

Este guia prioriza qualidade de produto. Comece com adaptadores locais, meca no
seu hardware e troque componentes por interfaces, sem acoplar a aplicacao a uma
biblioteca ou LLM especifica.

## 2. Stack recomendada

| Responsabilidade | Escolha inicial | Motivo |
| --- | --- | --- |
| Runtime | Python 3.12 x64 | Ecossistema e compatibilidade atual |
| UI/overlay | PySide6 | Qt nativo, sinais, threads e flags de janela |
| Microfone/loopback | SoundCard | WASAPI e loopback no Windows |
| STT | faster-whisper | CTranslate2, VAD e timestamps de palavra |
| Traducao | Interface LLM estruturada | Provider local ou remoto intercambiavel |
| Captura de tela | `mss` primeiro; DXCam opcional | Simplicidade; otimize apos medir |
| Encoding/mux | FFmpeg | MP4, H.264/AAC e ampla interoperabilidade |
| Persistencia | SQLite | Local, transacional e pesquisavel |
| Configuracao | Pydantic Settings | Tipagem, validacao e variaveis de ambiente |
| Hotkeys | Win32 `RegisterHotKey` | Comportamento global previsivel no Windows |
| Metricas | psutil + logging estruturado | CPU, RAM, filas, latencia e diagnostico |
| Testes | pytest + pytest-qt | Dominio, integracao e UI |
| Pacote | PyInstaller + instalador | Distribuicao sem exigir Python do usuario |

Antes de fixar versoes, confirme a compatibilidade do Python, CUDA, FFmpeg e do
modelo escolhido. Para uma primeira versao CPU, use um modelo Whisper pequeno;
para qualidade superior em GPU, avance somente depois de medir memoria e latencia.

## 3. Pre-requisitos e criacao do projeto

Instale Python 3.12, Git e FFmpeg no Windows. Instale tambem Docker Desktop com
containers Linux para hospedar os servicos de IA. Confirme no PowerShell:

```powershell
python --version
ffmpeg -version
git --version
docker version
docker compose version
```

Esses comandos nao instalam nada: apenas provam que cada fronteira esta acessivel.
Python executa a aplicacao; FFmpeg codifica e inspeciona os replays; Git registra
mudancas reproduziveis; Docker e Compose iniciam e coordenam o servidor de LLM.

Crie o projeto e o ambiente nativo da aplicacao:

```powershell
New-Item -ItemType Directory -Path E:\StreamingProject -Force
Set-Location E:\StreamingProject
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

O bloco cria uma pasta, entra nela, isola as dependencias em `.venv`, ativa esse
ambiente e atualiza o instalador de pacotes. As bibliotecas ainda nao sao instaladas
uma a uma: a secao 4 primeiro as registra em `pyproject.toml`, que sera a fonte
unica para instalacao e lock. Isso evita que o ambiente real divirja do projeto.

As dependencias declaradas no primeiro checkpoint tem responsabilidades deliberadas:

| Dependencia | Para que serve | Por que entra no projeto |
| --- | --- | --- |
| `PySide6` | Interface, janelas e sinais Qt | Permite overlay nativo, sempre no topo e integrado ao loop de eventos do Windows |
| `soundcard` | Captura microfone e loopback por WASAPI | Mantem as duas fontes identificadas sem escrever a camada de audio do zero |
| `numpy` | Arrays e transformacoes numericas | E o formato eficiente usado para PCM, resampling e entrada do STT |
| `faster-whisper` | Transcricao local de fala | Usa CTranslate2 para reduzir custo e latencia do Whisper em CPU/GPU |
| `mss` | Captura de tela | Oferece um primeiro adaptador simples antes de otimizar com APIs mais especificas |
| `pydantic-settings` | Configuracao tipada e validada | Impede valores invalidos e centraliza variaveis com prefixo `LCB_` |
| `psutil` | Metricas de CPU, RAM, disco e processos | Alimenta diagnostico e degradacao controlada sob pressao de recursos |
| `httpx` | Cliente HTTP | Conecta o aplicativo Windows ao servidor de traducao local ou centralizado |
| `keyring` | Acesso ao cofre de credenciais | Guarda chaves no Windows Credential Manager em vez de arquivos de texto |
| `pytest` | Testes automatizados | Verifica regras e regressao sem depender de uma execucao manual completa |
| `pytest-qt` | Testes de widgets e sinais Qt | Testa a UI respeitando o loop de eventos, sem `sleep` arbitrario |
| `ruff` | Lint e verificacoes de estilo | Detecta erros simples cedo e mantem o codigo consistente com baixo custo |
| `mypy` | Analise estatica de tipos | Encontra incompatibilidades entre contratos antes que virem falhas em runtime |
| `pip-tools` | Resolucao e lock de dependencias | Transforma dependencias diretas em versoes transitivas reproduziveis com hashes |

SQLite nao aparece no `pip install` porque ja faz parte da biblioteca padrao do
Python. FFmpeg e instalado como executavel externo porque codificacao multimidia
nao deve ficar acoplada ao processo da interface.

Captura de audio/tela, STT, overlay, hotkeys, SQLite, FFmpeg e a interface rodam no
Windows. Docker fica restrito aos servidores de IA acessados por HTTP. Essa divisao
preserva acesso ao hardware e permite que uma unica instancia de modelo atenda um
ou mais clientes Windows.

Nao instale CUDA por tentativa. Primeiro rode CPU, identifique a GPU e confirme a
compatibilidade do CTranslate2 e do runtime de containers antes de habilita-la.

### 3.1 Servidor de LLM em Docker

Prepare esta infraestrutura perto do inicio para validar a topologia, mas conecte
a traducao real somente no M04. Comece com Ollama por oferecer imagem Docker e API
compativel com partes da API OpenAI. O adaptador da aplicacao continua generico e
aceita qualquer servidor que cumpra o contrato configurado.

No M00, crie primeiro `.env.example`, que documenta os valores locais sem depender
do estado de um terminal:

```dotenv
OLLAMA_IMAGE=ollama/ollama:latest
OLLAMA_BIND=127.0.0.1:11434
LCB_TRANSLATION_BASE_URL=http://127.0.0.1:11434/v1
LCB_TRANSLATION_API_KEY=ollama
LCB_TRANSLATION_MODEL=qwen3:4b
```

Copie o template para a configuracao local e proteja essa copia no `.gitignore`:

```powershell
Copy-Item .env.example .env
```

```gitignore
.env
.env.*
!.env.example
```

O `.env.example` e versionado para documentar as chaves; o `.env` nao e versionado
porque varia por maquina. O modelo nao e segredo, mas e configuracao persistente e
nao deve depender de `$modelName` ou de outro valor temporario do PowerShell. Chaves
reais continuam no Credential Manager ou no secret store: ignorar `.env` no Git
reduz risco, mas nao o transforma em cofre.

Em seguida, crie `infra/llm/compose.yaml` seguindo este modelo:

Path: infra/llm/compose.yaml
```yaml
services:
  translation-llm:
    image: ${OLLAMA_IMAGE}
    restart: unless-stopped
    ports:
      - "${OLLAMA_BIND}:11434"
    volumes:
      - ollama-models:/root/.ollama

  model-loader:
    image: ${OLLAMA_IMAGE}
    depends_on:
      - translation-llm
    environment:
      OLLAMA_HOST: http://translation-llm:11434
    command: ["pull", "${LCB_TRANSLATION_MODEL}"]

volumes:
  ollama-models:
```

O servico `translation-llm` executa a API e `model-loader` instala somente o modelo
indicado no `.env`. Separar essas responsabilidades evita hardcode no comando e
download silencioso ao iniciar o servidor. Imagem e bind tambem vem do `.env`;
`restart` recupera o processo e o volume preserva modelos entre containers.

Durante o laboratorio inicial, `latest` reduz atrito. Antes de compartilhar o
ambiente ou liberar uma versao, substitua-o por uma tag ou digest testado e registre
a escolha em ADR.

Use `qwen3:4b` como primeiro modelo. Ele ocupa cerca de 2,5 GB na distribuicao
quantizada Q4_K_M do Ollama, usa licenca Apache 2.0 e declara suporte a mais de 100
idiomas e dialetos, incluindo traducao multilingue. Quatro bilhoes de parametros
oferecem um ponto de partida melhor que modelos muito pequenos para preservar nomes,
termos tecnicos e contexto, sem exigir de imediato a memoria de variantes maiores.
Isso e uma baseline de laboratorio, nao uma escolha definitiva de produto.

Inicie o servidor, baixe o modelo e valide a API:

```powershell
docker compose --env-file .\.env -f .\infra\llm\compose.yaml config
docker compose --env-file .\.env -f .\infra\llm\compose.yaml `
  up -d translation-llm
Invoke-RestMethod http://127.0.0.1:11434/api/tags
docker compose --env-file .\.env -f .\infra\llm\compose.yaml `
  run --rm model-loader
docker compose --env-file .\.env -f .\infra\llm\compose.yaml `
  logs --tail 100 translation-llm
```

`config` valida YAML e interpolacao antes de iniciar; `up -d` inicia a API;
`Invoke-RestMethod` confirma que ela esta pronta; `model-loader` le o nome do `.env`
e baixa exatamente esse modelo; e `logs` mostra a causa observavel caso algo falhe.
Essa ordem separa configuracao, infraestrutura, modelo e aplicativo.

No M04, teste `qwen3:4b` com falas reais em portugues, ingles e outros idiomas do
publico alvo. Registre RAM/VRAM, latencia p95, aderencia ao JSON e qualidade. Se nao
atingir a meta de latencia, compare uma variante menor; se perder significado ou
termos tecnicos e houver memoria disponivel, compare `qwen3:8b`. Para traducao em
tempo real, desative o modo de raciocinio quando a API usada oferecer esse controle,
pois tokens de pensamento aumentam latencia sem fazer parte da legenda. So altere a
baseline quando o benchmark demonstrar ganho. Edite o `.env` para trocar o modelo
ou endpoint: `BASE_URL` permite migrar de instancia local para central sem alterar
codigo; `API_KEY` uniformiza o contrato do cliente; e `MODEL` torna explicita a
versao de inferencia que afeta qualidade, latencia e cache.

A chave acima e apenas o valor exigido pelo cliente compativel e e ignorada pelo
Ollama local. Mesmo assim, nunca registre headers ou segredos reais em logs.
Confirme `/v1/chat/completions` e resposta JSON antes de integrar a pipeline.

Para centralizar o servidor em outra maquina, altere `LCB_TRANSLATION_BASE_URL`
para o DNS interno do servico. Nao exponha a porta 11434 diretamente na internet:
coloque o endpoint atras de rede privada e, quando cruzar maquinas, reverse proxy
com TLS, autenticacao, limites de requisicao e logs sem conteudo. O aplicativo deve
usar timeout, circuit breaker e fallback para a transcricao original quando o
servidor estiver indisponivel. Envie apenas texto final necessario, nunca audio.

O volume `ollama-models` conserva os downloads. `docker compose down` para o
servico sem apagar modelos; `docker compose down --volumes` remove-os e so deve ser
usado de forma deliberada. Comece em CPU. Habilite GPU apenas seguindo a matriz e
as instrucoes oficiais do host, depois de medir que o ganho compensa a complexidade.

### 3.2 Ferramentas basicas que voce deve dominar

- ambiente virtual, imports, excecoes, context managers, dataclasses e typing;
- Git: `status`, `diff`, commits pequenos, branches e `bisect` para regressao;
- `pytest`, fixtures, doubles/fakes e diferenca entre teste unitario e integracao;
- logging estruturado, debugger, profiler e leitura de stack trace;
- processos, threads, filas limitadas, timeout, cancelamento e backpressure;
- formatos PCM/WAV, sample rate, canais, codec, container, PTS e mux;
- SQL e transacoes; HTTP, JSON Schema, retry e idempotencia.

Nao e preciso dominar tudo antes de comecar. O plano da secao 20 introduz cada
assunto quando ele passa a ser necessario.

## 4. Comece pequeno: primeira versao executavel

A estrutura completa deste aplicativo e um destino arquitetural, nao uma lista de
pastas para criar de uma vez. Comece com um pacote que apenas inicia, registra uma
mensagem e passa por um teste. Esse primeiro circuito confirma Python, imports,
logging, testes e ferramentas antes de introduzir Qt, audio ou modelos pesados.

### 4.1 Checkpoint M00: fundacao minima

O M00 deve ser feito como uma sequencia de pequenos experimentos. Depois de cada
passo, observe o resultado e so avance se entender por que ele passou. Nenhum passo
cria varios arquivos de codigo ao mesmo tempo.

#### Passo 1 - Crie uma pasta por vez

```powershell
New-Item -ItemType Directory -Force -Path .\src
```

`src` separa codigo instalavel de arquivos de suporte. Confirme que a pasta existe
antes de continuar:

```powershell
Get-Item .\src
```

Agora crie apenas a pasta do pacote:

```powershell
New-Item -ItemType Directory -Force -Path .\src\live_caption_bridge
```

Ela recebera o codigo Python. Depois crie a pasta de testes unitarios:

```powershell
New-Item -ItemType Directory -Force -Path .\tests
```

Ela ficara isolada de audio, tela e rede. Por fim, crie o lugar do registro do marco:

```powershell
New-Item -ItemType Directory -Force -Path .\docs\lab
```

Neste momento nao crie `domain`, `ports`, `adapters`, `services` ou `ui`. Essas
fronteiras so aparecem quando um comportamento real exigir separacao.

#### Passo 2 - Crie o README antes da configuracao

Crie somente `README.md`:

```powershell
New-Item -ItemType File -Force -Path .\README.md
```

Abra o arquivo e escreva apenas:

Path: README.md
```markdown
# LiveCaptionBridge

Aplicativo Windows para legendas simultaneas e replay recente.
```

O README existe antes do pacote porque o build vai usa-lo como descricao publica.
Ele tambem oferece uma primeira verificacao manual: o projeto tem um objetivo
legivel antes de acumular implementacao.

#### Passo 3 - Monte o `pyproject.toml` em camadas

Crie somente o arquivo vazio:

```powershell
New-Item -ItemType File -Force -Path .\pyproject.toml
```

Abra-o no editor. Adicione primeiro apenas o build backend:

Path: pyproject.toml
```toml
[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"
```

Esse bloco diz qual ferramenta transformara o pacote em uma instalacao Python. O
arquivo ainda nao descreve o aplicativo. Verifique apenas a sintaxe TOML:

```powershell
python -c "import tomllib; tomllib.load(open('pyproject.toml','rb')); print('TOML valido')"
```

Agora adicione os metadados do projeto:

Path: pyproject.toml
```toml
[project]
name = "live-caption-bridge"
version = "0.1.0"
description = "Legendas simultaneas e replay recente no Windows"
readme = "README.md"
requires-python = ">=3.12"
```

Esses campos identificam o pacote, limitam a faixa de Python e apontam para o
README. Rode novamente o mesmo comando de sintaxe antes de acrescentar outra secao.

Adicione agora somente as dependencias de runtime:

Path: pyproject.toml
```toml
dependencies = [
  "PySide6",
  "soundcard",
  "numpy",
  "faster-whisper",
  "mss",
  "pydantic-settings",
  "psutil",
  "httpx",
  "keyring",
]
```

Este bloco liga cada necessidade do produto a uma biblioteca, mas ainda nao instala
nada. A tabela da secao 3 explica o papel de cada nome; o objetivo aqui e tornar o
projeto a fonte de verdade, em vez de depender do comando de `pip` digitado antes.

Adicione as ferramentas usadas somente durante desenvolvimento:

Path: pyproject.toml
```toml
[project.optional-dependencies]
dev = ["pytest", "pytest-qt", "ruff", "mypy", "pip-tools"]
```

O extra `dev` evita colocar lint e testes no produto distribuido. Separe essa ideia
da lista anterior: runtime e o que o programa precisa para funcionar; dev e o que
nos ajuda a construir e verificar o programa.

Adicione a entrada de terminal:

Path: pyproject.toml
```toml
[project.scripts]
live-caption-bridge = "live_caption_bridge.main:main"
```

Ela conectara um comando amigavel a uma funcao Python, mas so funcionara depois que
`main.py` existir. Essa dependencia entre etapas explica por que nao configuramos o
script antes de criar o pacote.

Adicione a descoberta do codigo em `src`:

Path: pyproject.toml
```toml
[tool.setuptools.packages.find]
where = ["src"]
```

Sem isso, o backend poderia procurar o pacote na raiz errada. Valide o TOML uma
ultima vez; erros de indentacao ou nomes de secao devem ser corrigidos agora.

#### Passo 4 - Crie o pacote, um arquivo por vez

Crie `src/live_caption_bridge/__init__.py`:

```powershell
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\__init__.py
```

Digite apenas a docstring:

Path: src/live_caption_bridge/__init__.py
```python
"""LiveCaptionBridge."""
```

O arquivo marca o diretorio como pacote sem iniciar UI ou modelo durante um import.

Crie `src/live_caption_bridge/main.py` em um comando separado:

```powershell
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\main.py
```

Adicione o menor ponto de entrada que registra vida e termina com sucesso:

Path: src/live_caption_bridge/main.py
```python
import logging

LOGGER = logging.getLogger(__name__)


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    LOGGER.info("LiveCaptionBridge iniciado")
    return 0
```

O logging torna o primeiro efeito observavel; o inteiro permite que terminal,
launcher e teste distingam sucesso de falha. Ainda nao abrimos Qt nem carregamos
Whisper, porque isso introduziria problemas de hardware antes de validar a base.

Crie `src/live_caption_bridge/__main__.py` separadamente:

```powershell
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\__main__.py
```

Adicione apenas a delegacao:

Path: src/live_caption_bridge/__main__.py
```python
from live_caption_bridge.main import main

raise SystemExit(main())
```

Ela habilita `python -m live_caption_bridge` sem duplicar a inicializacao.

#### Passo 5 - Crie um teste antes de adicionar comportamento

Crie somente `tests/test_main.py`:

```powershell
New-Item -ItemType File -Force -Path .\tests\test_main.py
```

Adicione o teste:

Path: tests/test_main.py
```python
import logging

from live_caption_bridge.main import main


def test_main_inicia_com_sucesso(caplog) -> None:
    with caplog.at_level(logging.INFO):
        exit_code = main()

    assert exit_code == 0
    assert "LiveCaptionBridge iniciado" in caplog.text
```

Ele verifica o retorno e o log sem abrir janela, usar audio ou depender de rede.
`caplog` captura o mecanismo de logging do pytest, tornando o teste repetivel.

#### Passo 6 - Instale e valide uma coisa por vez

```powershell
python -m pip install pip-tools
```

Instale `pip-tools` explicitamente no ambiente ativo. Usar `python -m pip` garante
que o pacote vai para o mesmo interpretador que executara o projeto; instalar no
Python global nao disponibiliza o comando dentro de `.venv`.

No Windows, prefira `python` depois de ativar `.venv` ou use o caminho completo
`\.venv\Scripts\python.exe`. O launcher `py` pode selecionar outra instalacao e
deixar o pacote editavel registrado no Python global.

```powershell
python -m pip install --editable ".[dev]"
```

A instalacao editavel registra o pacote no ambiente sem copiar o codigo; por isso,
as proximas alteracoes aparecem imediatamente no teste.

```powershell
python -m piptools compile --extra dev --generate-hashes `
  --output-file requirements.lock pyproject.toml
```

O modulo `piptools` evita depender de um executavel separado no `PATH`. Agora as
dependencias transitivas recebem versoes e hashes. O lockfile documenta o ambiente
que funcionou, mas nao substitui a compreensao das dependencias diretas.

```powershell
python -m live_caption_bridge
```

Este comando valida o caminho de entrada do modulo e deve registrar a mensagem de
inicializacao.

```powershell
pytest
```

O teste confirma o comportamento minimo antes de qualquer integracao externa.

```powershell
ruff check .
```

O lint procura erros simples e inconsistencias de estilo que nao exigem executar a
aplicacao.

```powershell
mypy src
```

A checagem de tipos confirma os contratos Python do pacote. Pare e investigue o
primeiro comando que falhar; nao empilhe correcoes de etapas diferentes.

Somente depois de cada comando passar, registre `docs/lab/M00-fundacao.md` e avance
para o M01. O marco termina quando outra pessoa consegue repetir esse percurso,
nao quando a arvore final inteira foi criada antecipadamente.

### 4.3 Estrutura alvo, nao tarefa imediata

Ao final dos marcos, a organizacao devera convergir para:

```text
StreamingProject/
  .env.example
  .gitignore
  pyproject.toml
  requirements.lock
  README.md
  infra/
    llm/
      compose.yaml
  docs/
    architecture.md
    troubleshooting.md
    adr/
    lab/
  src/
    live_caption_bridge/
      __init__.py
      __main__.py
      main.py
      domain/
        models.py
        events.py
      ports/
        audio.py
        speech.py
        translation.py
        recorder.py
        repository.py
      services/
        caption_pipeline.py
        replay_service.py
        resource_governor.py
      adapters/
        soundcard_audio.py
        whisper_stt.py
        llm_translation.py
        ffmpeg_recorder.py
        sqlite_repository.py
        windows_hotkeys.py
      ui/
        main_window.py
        overlay.py
        history_view.py
        settings_view.py
      infrastructure/
        settings.py
        logging.py
        lifecycle.py
  tests/
    unit/
    integration/
    e2e/
```

`domain` preserva regras sem bibliotecas externas; `ports` descreve o que o nucleo
precisa; `adapters` conversa com hardware e providers; `services` coordena casos de
uso; `ui` permanece no thread principal; e `infrastructure` cuida de inicializacao
e configuracao. Essa separacao e o destino porque facilita testes e substituicoes,
mas cria-la antecipadamente produziria apenas pastas sem comportamento.

Quando o checkpoint M00 estiver verde, o M01 introduz os primeiros modelos de
dominio. Eles serao a necessidade concreta que cria `domain/` nesse marco.

## Caminho principal de implementacao

Os marcos abaixo sao o percurso executavel do projeto. Cada um parte do resultado
verde do anterior e termina com uma demonstracao verificavel. As referencias tecnicas
que aparecem depois servem para consulta no momento em que a etapa as torna necessarias;
elas nao sao uma segunda lista de tarefas.

## M01 - Domínio e overlay falso

**Ponto de partida.** M00 deixa um pacote executável, mas ainda não existe um dado que represente uma legenda. Neste marco vamos atravessar o caminho mínimo modelo -> porta -> janela, sem microfone, rede ou banco. Isso reduz as causas possíveis quando o primeiro texto aparecer na tela.

### M01.0 Prepare o primeiro teste

Antes de criar o modelo, crie a pasta **tests/** e o arquivo
**tests/test_models.py**. O prefixo **test_** é reconhecido pelo pytest; o
`assert` compara o resultado real com o comportamento que queremos preservar. Este
primeiro teste não testa a aplicação inteira: ele verifica somente que a origem do
áudio tem dois valores distintos.

~~~powershell
New-Item -ItemType Directory -Force -Path .\tests
New-Item -ItemType File -Force -Path .\tests\test_models.py
~~~

Path: tests/test_models.py
~~~python
from live_caption_bridge.domain.models import AudioSource


def test_audio_sources_are_distinct() -> None:
    assert AudioSource.MICROPHONE != AudioSource.SYSTEM
~~~

O import ainda falhará até o modelo existir. Isso é intencional: primeiro escrevemos
o comportamento esperado, depois criamos o menor código que o satisfaz. Rode o teste
com o mesmo interpretador do ambiente ativo:

~~~powershell
python -m pytest tests/test_models.py -q
~~~

Se aparecer `ModuleNotFoundError`, não altere o teste para contornar o erro; confirme
que a instalação editável do M00 foi feita no venv correto. Quando o teste passar,
continue para o arquivo de domínio.

### M01.1 Primeiro contrato de dados

Crie primeiro a pasta e o arquivo, separadamente, para que a estrutura nasça junto
com a necessidade que a motivou:

~~~powershell
New-Item -ItemType Directory -Force -Path .\src\live_caption_bridge\domain
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\domain\models.py
~~~

Crie somente **src/live_caption_bridge/domain/models.py**. Comece pelo tipo que explica uma decisão importante: a legenda precisa saber se veio do microfone ou do áudio do sistema. Use um enum antes de criar classes maiores, porque ele impede strings inconsistentes espalhadas pelo código.

Path: src/live_caption_bridge/domain/models.py
~~~python
from enum import StrEnum

class AudioSource(StrEnum):
    MICROPHONE = "microphone"
    SYSTEM = "system"
~~~

O teste criado em M01.0 já cobre esse primeiro tipo. Depois de salvar o enum, rode-o
novamente para confirmar que a implementação agora satisfaz o contrato:

~~~powershell
python -m pytest tests/test_models.py -q
~~~

O resultado esperado é dois valores distintos. Se esse teste falhar, não crie ainda AudioChunk: o restante do projeto dependerá desta identidade.

### M01.2 AudioChunk: primeiro dado que atravessa o sistema

AudioChunk transporta amostras PCM e timestamps entre captura, VAD e STT. Ele não
conhece SoundCard nem nenhuma biblioteca — é apenas um recipiente de dados. Abra o
arquivo de modelos e adicione a dataclass abaixo de AudioSource:

Path: src/live_caption_bridge/domain/models.py
~~~python
from dataclasses import dataclass
from enum import StrEnum


class AudioSource(StrEnum):
    MICROPHONE = "microphone"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class AudioChunk:
    source: AudioSource
    samples: bytes
    sample_rate: int
    channels: int
    started_ns: int
    ended_ns: int
~~~

`samples` carrega PCM bruto em bytes, sem depender de NumPy ainda. `started_ns` e
`ended_ns` usam `time.monotonic_ns()` para ordenação — relógio de parede pode mudar
e não serve para sincronia. `frozen=True` impede que um worker altere o chunk depois
de publicado; `slots=True` reduz memória para muitos objetos em trânsito.

Salve o arquivo e crie o teste abaixo para verificar que AudioChunk preserva a origem
e rejeita mutação:

Path: tests/test_models.py
~~~python
from dataclasses import FrozenInstanceError
from live_caption_bridge.domain.models import AudioChunk, AudioSource


def test_audio_chunk_preserves_source_and_is_immutable() -> None:
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"audio",
        sample_rate=16_000,
        channels=1,
        started_ns=10,
        ended_ns=20,
    )
    assert chunk.source is AudioSource.MICROPHONE
    assert chunk.ended_ns > chunk.started_ns
    try:
        chunk.channels = 2
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("AudioChunk deve ser imutável")
~~~

Rode o teste — ele deve passar. Se falhar, não avance: o resto da pipeline depende
deste contrato.

~~~powershell
python -m pytest tests/test_models.py -q
~~~

### M01.3 Transcript: resultado do reconhecimento

Com AudioChunk validado, adicione Transcript ao mesmo arquivo. Ele carrega o texto
que o STT reconheceu, o idioma detectado e os mesmos timestamps monotônicos do chunk
que o originou:

Path: src/live_caption_bridge/domain/models.py
~~~python
@dataclass(frozen=True, slots=True)
class Transcript:
    source: AudioSource
    text: str
    language: str
    started_ns: int
    ended_ns: int
    confidence: float | None = None
~~~

`confidence` é opcional porque alguns modelos não a expõem. Ainda assim o campo
existe para que o pipeline possa registrar incerteza sem mudar o contrato.

Adicione o teste correspondente:

Path: tests/test_models.py
~~~python
from live_caption_bridge.domain.models import Transcript


def test_transcript_holds_text_and_language() -> None:
    t = Transcript(
        source=AudioSource.SYSTEM,
        text="Hello world",
        language="en",
        started_ns=10,
        ended_ns=110,
    )
    assert t.text == "Hello world"
    assert t.language == "en"
    assert t.source is AudioSource.SYSTEM
~~~

Rode o arquivo inteiro novamente. Os dois testes devem passar.

### M01.4 Caption: legenda exibível

Caption combina original, tradução opcional e dados de idioma. Original e tradução
ficam separados para que uma falha externa (tradução offline) nunca apague o que foi
reconhecido:

Path: src/live_caption_bridge/domain/models.py
~~~python
@dataclass(frozen=True, slots=True)
class Caption:
    original: str
    translated: str
    source_lang: str
    target_lang: str
    started_ns: int
    ended_ns: int
~~~

Teste que Caption preserva original e tradução:

Path: tests/test_models.py
~~~python
from live_caption_bridge.domain.models import Caption


def test_caption_separates_original_from_translation() -> None:
    c = Caption(
        original="Olá mundo",
        translated="Hello world",
        source_lang="pt",
        target_lang="en",
        started_ns=10,
        ended_ns=110,
    )
    assert c.original == "Olá mundo"
    assert c.translated == "Hello world"
    assert c.source_lang == "pt"
    assert c.target_lang == "en"
~~~

Valide o arquivo completo:

~~~powershell
python -m pytest tests/test_models.py -q
~~~

### M01.5 Uma porta e um fake

Crie a porta somente quando o modelo passar:

~~~powershell
New-Item -ItemType Directory -Force -Path .\src\live_caption_bridge\ports
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\ports\caption_sink.py
~~~

O Protocol a seguir descreve a necessidade do domínio sem importar PySide6 — qualquer
adaptador que implementar `publish(caption)` poderá receber legendas:

Path: src/live_caption_bridge/ports/caption_sink.py
~~~python
from typing import Protocol

from live_caption_bridge.domain.models import Caption


class CaptionSink(Protocol):
    def publish(self, caption: Caption) -> None: ...
~~~

Agora crie o fake que implementa esse protocolo em memória. Ele permite testar o fluxo
em milissegundos e deixa a janela real para uma etapa posterior:

~~~powershell
New-Item -ItemType File -Force -Path .\tests\fakes.py
~~~

Path: tests/fakes.py
~~~python
from live_caption_bridge.domain.models import Caption


class FakeCaptionSink:
    def __init__(self) -> None:
        self.last: Caption | None = None

    def publish(self, caption: Caption) -> None:
        self.last = caption
~~~

Crie o teste que publica uma Caption e verifica que `sink.last` é a mesma instância.
Esse teste prova o contrato antes de uma janela real participar:

Path: tests/test_caption_sink.py
~~~python
from live_caption_bridge.domain.models import Caption
from tests.fakes import FakeCaptionSink


def test_fake_sink_receives_caption() -> None:
    sink = FakeCaptionSink()
    caption = Caption(
        original="Olá",
        translated="Hello",
        source_lang="pt",
        target_lang="en",
        started_ns=0,
        ended_ns=100,
    )
    sink.publish(caption)
    assert sink.last is caption
~~~

~~~powershell
python -m pytest tests -q
~~~

Só avance quando o fake receber exatamente a legenda que o teste publicou.

### M01.6 Janela mínima e uma mudança visual por vez

Depois de a porta passar, crie a pasta da UI e o teste de integração separadamente:

~~~powershell
New-Item -ItemType Directory -Force -Path .\src\live_caption_bridge\ui
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\ui\overlay.py
New-Item -ItemType Directory -Force -Path .\tests\integration
New-Item -ItemType File -Force -Path .\tests\integration\test_overlay.py
~~~

Crie o overlay como um QWidget frameless e translúcido que exibe legendas:

Path: src/live_caption_bridge/ui/overlay.py
~~~python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout


class Overlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._label = QLabel("Teste de legenda")
        self._label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self._label)

    def text(self) -> str:
        return self._label.text()
~~~

Primeiro prove que o widget abre e fecha. O fixture **qtbot** do pytest-qt encerra o
widget e evita sleeps arbitrários:

Path: tests/integration/test_overlay.py
~~~python
def test_overlay_starts_with_placeholder(qtbot) -> None:
    from live_caption_bridge.ui.overlay import Overlay

    overlay = Overlay()
    qtbot.addWidget(overlay)
    assert overlay.text() == "Teste de legenda"
~~~

~~~powershell
python -m pytest tests/integration -q
~~~

Depois de o placeholder aparecer, substitua a string fixa por um método que recebe uma
Caption do sink. Adicione o import no topo do arquivo:

Path: src/live_caption_bridge/ui/overlay.py
~~~python
from live_caption_bridge.domain.models import Caption
~~~

Depois adicione o método à classe Overlay:

Path: src/live_caption_bridge/ui/overlay.py
~~~python
    def display_caption(self, caption: Caption) -> None:
        self._label.setText(
            caption.translated or caption.original
        )
~~~

E altere o teste para publicar uma legenda:

Path: tests/integration/test_overlay.py
~~~python
from live_caption_bridge.domain.models import Caption


def test_overlay_displays_caption(qtbot) -> None:
    from live_caption_bridge.ui.overlay import Overlay

    overlay = Overlay()
    qtbot.addWidget(overlay)
    caption = Caption(
        original="Olá",
        translated="Hello",
        source_lang="pt",
        target_lang="en",
        started_ns=0,
        ended_ns=100,
    )
    overlay.display_caption(caption)
    assert "Hello" in overlay.text()
~~~

~~~powershell
python -m pytest tests -q
~~~

### M01.7 Execução manual do overlay

Com o widget criado e testado, adicione um ponto de entrada para ver a janela fora dos
testes. Abra `src/live_caption_bridge/ui/overlay.py` e acrescente no final:

Path: src/live_caption_bridge/ui/overlay.py
~~~python
import sys

from PySide6.QtWidgets import QApplication


def main() -> None:
    app = QApplication(sys.argv)
    overlay = Overlay()
    overlay.show()
    caption = Caption(
        original="Olá mundo",
        translated="Hello world",
        source_lang="pt",
        target_lang="en",
        started_ns=0,
        ended_ns=100,
    )
    overlay.display_caption(caption)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
~~~

`main()` cria um `QApplication`, instancia o Overlay e chama `show()` — sem isso a
janela nunca aparece. O `if __name__ == "__main__"` permite executar diretamente:

~~~powershell
python -m live_caption_bridge.ui.overlay
~~~

Uma janela frameless, translúcida e sempre-no-topo deve aparecer com "Hello world".
Feche com Alt+F4 ou pelo console. Se nada aparecer, confirme que PySide6 está
instalado e que o ambiente `.venv` está ativo.

Quando isso funcionar, habilite translucidez, sempre-no-topo e click-through, uma flag
por vez. Cada flag muda o comportamento do Windows e pode afetar DPI, foco e
fechamento; por isso a validação deve ocorrer imediatamente, sem sleep e sem workers
dentro do widget.

**Checkpoint M01.** O domínio passa sem importar Qt, o teste de UI fecha a janela de
forma determinística e `python -m live_caption_bridge.ui.overlay` exibe uma legenda na
tela. Registre a evidência em **docs/lab/M01-dominio-overlay.md** antes de iniciar o
áudio.

Leitura: [dataclasses](https://docs.python.org/3/library/dataclasses.html),
[Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol),
[Qt for Python](https://doc.qt.io/qtforpython-6/) e
[pytest-qt](https://pytest-qt.readthedocs.io/en/latest/).

## M02 - Uma fonte de áudio observável

**Ponto de partida.** M01 prova uma legenda sem hardware. Agora o objetivo é produzir
cinco segundos de áudio identificável e verificável, sem STT. O WAV é escolhido como
primeira evidência porque pode ser aberto por ferramentas independentes do nosso
código.

### M02.1 Contrato da porta de áudio

Crie as pastas e arquivos:

~~~powershell
New-Item -ItemType Directory -Force -Path .\src\live_caption_bridge\adapters
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\ports\audio.py
New-Item -ItemType File -Force -Path .\src\live_caption_bridge\adapters\soundcard_audio.py
New-Item -ItemType File -Force -Path .\tests\test_audio_port.py
~~~

A porta descreve o que o domínio precisa sem nomear SoundCard. Qualquer adaptador que
cumprir este Protocol pode ser usado:

Path: src/live_caption_bridge/ports/audio.py
~~~python
from typing import Protocol

from live_caption_bridge.domain.models import AudioChunk


class AudioDeviceInfo:
    def __init__(self, name: str, id: str) -> None:
        self.name = name
        self.id = id


class AudioSourcePort(Protocol):
    def list_devices(self) -> list[AudioDeviceInfo]: ...
    def open(self, device_id: str, sample_rate: int = 16000,
             channels: int = 1) -> None: ...
    def read_chunk(self) -> AudioChunk: ...
    def close(self) -> None: ...
~~~

Agora crie um adaptador mínimo que apenas enumera dispositivos. Ele serve para validar
que o SoundCard está funcional antes de escrever lógica de captura:

Path: src/live_caption_bridge/adapters/soundcard_audio.py
~~~python
import soundcard as sc


def list_devices() -> list[dict[str, str]]:
    mics = sc.all_microphones(include_loopback=True)
    return [{"name": mic.name, "id": mic.id} for mic in mics]


if __name__ == "__main__":
    for dev in list_devices():
        print(dev["name"], dev["id"])
~~~

Teste o contrato com um enumerador falso. Ele prova que a porta devolve nome e id sem
exigir microfone conectado:

Path: tests/test_audio_port.py
~~~python
from live_caption_bridge.ports.audio import AudioDeviceInfo


class FakeEnumerator:
    def list_devices(self) -> list[AudioDeviceInfo]:
        return [
            AudioDeviceInfo("Microphone (Realtek)", "mic1"),
            AudioDeviceInfo("Speakers (Realtek)", "speaker1"),
        ]


def test_enumerator_returns_name_and_id() -> None:
    enum = FakeEnumerator()
    devices = enum.list_devices()
    assert len(devices) == 2
    assert all(d.name and d.id for d in devices)
~~~

~~~powershell
python -m pytest tests/test_audio_port.py -q
~~~

Valide também o adaptador real manualmente:

~~~powershell
python -m live_caption_bridge.adapters.soundcard_audio
~~~

Deve listar seus microfones e speakers. Se a lista vier vazia, verifique permissões
de áudio do Windows. O dispositivo padrão não deve ser assumido, pois Bluetooth,
Remote Desktop e troca de headset alteram essa escolha.

### M02.2 Produtor com fila e parada

Crie o teste que prova a coordenação entre uma thread produtora, uma fila limitada e
um evento de parada. Nenhum áudio real é capturado — apenas a mecânica de
comunicação:

~~~powershell
New-Item -ItemType File -Force -Path .\tests\test_audio_worker.py
~~~

Path: tests/test_audio_worker.py
~~~python
import queue
import threading


def test_producer_delivers_three_blocks() -> None:
    q: queue.Queue = queue.Queue(maxsize=10)
    stop = threading.Event()
    blocks = []

    def producer() -> None:
        for _ in range(3):
            if stop.is_set():
                break
            q.put(b"block")
        stop.set()

    t = threading.Thread(target=producer)
    t.start()
    t.join()

    while not q.empty():
        blocks.append(q.get_nowait())

    assert len(blocks) == 3
    assert all(b == b"block" for b in blocks)
    assert stop.is_set()
~~~

~~~powershell
python -m pytest tests/test_audio_worker.py -q
~~~

A fila tem `maxsize` para impedir crescimento infinito se o consumidor ficar lento.

### M02.3 Grave um WAV e confirme metadados

Crie um script que abre o dispositivo padrão, captura cinco segundos e salva um WAV.
Não conecte a UI ainda: se o WAV estiver errado, a origem do problema fica isolada
no áudio:

Path: docs/lab/capture_test.py
~~~python
import wave
import soundcard as sc
import numpy as np

DURATION = 5
SAMPLE_RATE = 16000

mic = sc.default_microphone()
frames = mic.record(samplerate=SAMPLE_RATE, numframes=SAMPLE_RATE * DURATION)
audio = (np.int16(frames[:, 0] * 32767)).tobytes()

with wave.open("docs/lab/capture.wav", "wb") as w:
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(SAMPLE_RATE)
    w.writeframes(audio)
~~~

Execute e confira os metadados:

~~~powershell
python docs/lab/capture_test.py
python -c "import wave; w=wave.open('docs/lab/capture.wav'); print(w.getframerate(), w.getnchannels(), w.getnframes())"
~~~

Deve imprimir `16000 1 80000` (16000 Hz × 5 s). O arquivo `docs/lab/capture.wav` pode
ser aberto em qualquer player de áudio.

### M02.4 Função dBFS com testes

Crie uma função pura que calcula nível em dBFS a partir de bytes PCM. Isolar a
matemática do dispositivo evita culpar o driver quando o erro é numérico:

~~~powershell
New-Item -ItemType File -Force -Path .\tests\test_audio_level.py
~~~

Path: tests/test_audio_level.py
~~~python
import math
import struct


def dbfs(samples: bytes, sample_width: int = 2) -> float:
    if not samples:
        return -float("inf")
    max_possible = 2 ** (sample_width * 8 - 1)
    max_val = 0
    for i in range(0, len(samples), sample_width):
        val = abs(int.from_bytes(
            samples[i:i + sample_width], "little", signed=True))
        max_val = max(max_val, val)
    if max_val == 0:
        return -float("inf")
    return 20.0 * math.log10(max_val / max_possible)


def test_silence_returns_neg_inf() -> None:
    silence = struct.pack("<h", 0) * 100
    assert dbfs(silence) == -float("inf")


def test_half_amplitude_is_minus_6db() -> None:
    signal = struct.pack("<h", 16384) * 100
    assert abs(dbfs(signal) - (-6.02)) < 0.1


def test_clipping_is_0db() -> None:
    clip = struct.pack("<h", 32767) * 100
    assert abs(dbfs(clip) - 0) < 0.1
~~~

~~~powershell
python -m pytest tests/test_audio_level.py -q
~~~

Silêncio retorna `-inf` (sem sinal), metade da amplitude resulta ≈ −6 dBFS e o valor
máximo possível retorna 0 dBFS.

### M02.5 Worker encerrável com threading.Event

Agora mova a captura para uma thread que publica na fila e encerra com um
`threading.Event`. O worker tenta reabrir o dispositivo se ele falhar, em vez de
deixar o processo morrer:

~~~powershell
New-Item -ItemType File -Force -Path .\tests\test_audio_worker_stop.py
~~~

Path: tests/test_audio_worker_stop.py
~~~python
import queue
import threading


def test_worker_stops_on_event() -> None:
    q: queue.Queue = queue.Queue(maxsize=10)
    stop = threading.Event()

    def worker() -> None:
        while not stop.is_set():
            try:
                q.put(b"dummy", timeout=0.1)
            except queue.Full:
                pass

    t = threading.Thread(target=worker)
    t.start()
    stop.set()
    t.join(timeout=2)

    assert not t.is_alive()
~~~

~~~powershell
python -m pytest tests/test_audio_worker_stop.py -q
~~~

O worker loopa até o evento ser acionado. `timeout=0.1` no `put` impede que ele
trave se a fila estiver cheia. `t.join(timeout=2)` garante que o teste não congele se
o worker não parar.

**Checkpoint M02.** Um WAV de cinco segundos abre e seus metadados batem
(16000 Hz, 1 canal, 80000 frames), dBFS é coerente (silêncio = −inf, clipping = 0 dB),
a fila não cresce sem limite e o worker encerra com `threading.Event`. Registre em
**docs/lab/M02-audio.md**.

Leitura: [wave](https://docs.python.org/3/library/wave.html), [threading](https://docs.python.org/3/library/threading.html), [queue](https://docs.python.org/3/library/queue.html) e [SoundCard](https://soundcard.readthedocs.io/en/latest/).

## M03 - VAD, STT e legenda

**Ponto de partida.** M02 produz áudio, mas não sabe onde a fala começa e termina. Primeiro vamos transformar um WAV conhecido em texto; somente depois ligaremos o worker ao modelo. Assim podemos medir STT sem atribuir lentidão à captura.

### M03.1 VAD por energia com pre-roll

Path: src/live_caption_bridge/services/vad.py
~~~python
import math
import struct
from collections.abc import Sequence

from live_caption_bridge.domain.models import AudioChunk


def _rms_dbfs(samples: bytes, channels: int) -> float:
    if not samples:
        return -float("inf")
    fmt = "<" + "h" * (len(samples) // 2)
    try:
        values = struct.unpack(fmt, samples)
    except struct.error:
        return -float("inf")
    if not values:
        return -float("inf")
    sq_sum = sum(v * v for v in values)
    rms = math.sqrt(sq_sum / len(values)) / 32767.0
    if rms <= 0:
        return -float("inf")
    return 20.0 * math.log10(rms)


def rms_dbfs(samples: bytes, channels: int = 1) -> float:
    return _rms_dbfs(samples, channels)


Segment = tuple[int, int]


def segment_chunks(
    chunks: Sequence[AudioChunk],
    threshold_dbfs: float = -30.0,
    pre_roll_ns: int = 500_000_000,
    max_duration_ns: int = 30_000_000_000,
    min_silence_ns: int = 800_000_000,
) -> list[Segment]:
    if not chunks:
        return []
    segments: list[Segment] = []
    in_speech = False
    seg_start: int | None = None
    last_speech_end: int | None = None
    speech_timestamps: list[int] = []

    for chunk in chunks:
        energy = _rms_dbfs(chunk.samples, chunk.channels)
        is_speech = energy >= threshold_dbfs
        now = chunk.started_ns

        if is_speech:
            if not in_speech:
                speech_timestamps = [now]
                in_speech = True
                seg_start = now
            else:
                speech_timestamps.append(now)
            last_speech_end = chunk.ended_ns
        else:
            if in_speech:
                silence_duration = chunk.ended_ns - last_speech_end
                if silence_duration >= min_silence_ns:
                    dur = last_speech_end - seg_start
                    if dur > max_duration_ns:
                        last_speech_end = seg_start + max_duration_ns
                    segments.append(
                        (max(0, seg_start - pre_roll_ns), last_speech_end)
                    )
                    in_speech = False
                    seg_start = None

    if in_speech and seg_start is not None:
        end = last_speech_end if last_speech_end else seg_start
        if end - seg_start > max_duration_ns:
            end = seg_start + max_duration_ns
        segments.append((max(0, seg_start - pre_roll_ns), end))

    return segments
~~~

Path: tests/test_vad.py
~~~python
import struct

from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.services.vad import rms_dbfs, segment_chunks


def _silence_chunk(start_ns: int = 0, dur_ns: int = 1_000_000_000) -> AudioChunk:
    return AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=start_ns,
        ended_ns=start_ns + dur_ns,
    )


def _speech_chunk(start_ns: int = 0, dur_ns: int = 1_000_000_000) -> AudioChunk:
    samples = b"".join(
        struct.pack("<h", 10000) for _ in range(16000)
    )
    return AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=samples,
        sample_rate=16000,
        channels=1,
        started_ns=start_ns,
        ended_ns=start_ns + dur_ns,
    )


def test_rms_dbfs_silence_is_neg_inf() -> None:
    assert rms_dbfs(b"") == -float("inf")
    assert rms_dbfs(b"\x00\x00" * 100) == -float("inf")


def test_rms_dbfs_full_scale_is_zero() -> None:
    samples = struct.pack("<" + "h" * 100, *([32767] * 100))
    val = rms_dbfs(samples)
    assert abs(val) < 0.1


def test_segment_silence_yields_empty() -> None:
    chunks = [_silence_chunk(0), _silence_chunk(1_000_000_000)]
    assert segment_chunks(chunks) == []


def test_segment_speech_continuous() -> None:
    chunks = [_speech_chunk(0), _speech_chunk(1_000_000_000)]
    segs = segment_chunks(chunks, pre_roll_ns=0)
    assert len(segs) == 1
    assert segs[0][0] == 0
    assert segs[0][1] == 2_000_000_000


def test_segment_speech_with_pause_is_two_segments() -> None:
    c1 = _speech_chunk(0)
    c2 = _silence_chunk(1_000_000_000, dur_ns=2_000_000_000)
    c3 = _speech_chunk(3_000_000_000)
    segs = segment_chunks([c1, c2, c3], pre_roll_ns=0, min_silence_ns=1_500_000_000)
    assert len(segs) == 2


def test_segment_noise_stays_below_threshold() -> None:
    low = struct.pack("<h", 1)
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=low * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    assert segment_chunks([chunk], threshold_dbfs=-20.0) == []


def test_segment_max_duration_truncates() -> None:
    long = _speech_chunk(0, dur_ns=60_000_000_000)
    segs = segment_chunks([long], pre_roll_ns=0, max_duration_ns=30_000_000_000)
    assert len(segs) == 1
    assert segs[0][1] - segs[0][0] <= 30_000_000_000


def test_segment_pre_roll_shifts_start() -> None:
    c = _speech_chunk(5_000_000_000)
    segs = segment_chunks([c], pre_roll_ns=2_000_000_000)
    assert len(segs) == 1
    assert segs[0][0] == 3_000_000_000
~~~

Valide:

~~~powershell
python -m pytest tests/test_vad.py -q
~~~

### M03.2 Porta Speech e adaptador Whisper

Path: src/live_caption_bridge/ports/speech.py
~~~python
from typing import NamedTuple, Protocol

from live_caption_bridge.domain.models import AudioChunk


class SpeechSegment(NamedTuple):
    text: str
    language: str
    start_ns: int
    end_ns: int
    confidence: float | None = None


class SpeechPort(Protocol):
    def transcribe(self, chunk: AudioChunk) -> SpeechSegment: ...
~~~

Path: src/live_caption_bridge/adapters/whisper_stt.py
~~~python
import logging

from live_caption_bridge.domain.models import AudioChunk
from live_caption_bridge.ports.speech import SpeechSegment

logger = logging.getLogger(__name__)


class WhisperSTT:
    def __init__(self, model_size: str = "tiny", device: str = "cpu") -> None:
        self._model_size = model_size
        self._device = device
        self._model = None

    def _load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel

        self._model = WhisperModel(self._model_size, device=self._device)

    def transcribe(self, chunk: AudioChunk) -> SpeechSegment:
        import io
        import wave

        self._load()
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as w:
            w.setnchannels(chunk.channels)
            w.setsampwidth(2)
            w.setframerate(chunk.sample_rate)
            w.writeframes(chunk.samples)
        wav_buf.seek(0)
        segments, info = self._model.transcribe(wav_buf, beam_size=1)
        text = ""
        seg_start = chunk.started_ns
        seg_end = chunk.ended_ns
        confidence: float | None = None
        for s in segments:
            text += s.text + " "
            confidence = s.avg_logprob if hasattr(s, "avg_logprob") else None
        text = text.strip()
        if not text:
            text = ""
        return SpeechSegment(
            text=text,
            language=info.language if hasattr(info, "language") else "",
            start_ns=seg_start,
            end_ns=seg_end,
            confidence=confidence,
        )
~~~

Path: tests/test_speech.py
~~~python
from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.ports.speech import SpeechPort, SpeechSegment


class FakeSTT:
    def __init__(self, text: str = "hello world", lang: str = "en") -> None:
        self._text = text
        self._lang = lang
        self.called_with: list[AudioChunk] = []

    def transcribe(self, chunk: AudioChunk) -> SpeechSegment:
        self.called_with.append(chunk)
        return SpeechSegment(
            text=self._text,
            language=self._lang,
            start_ns=chunk.started_ns,
            end_ns=chunk.ended_ns,
            confidence=0.9,
        )


def test_fake_stt_returns_fixed_text() -> None:
    stt: SpeechPort = FakeSTT(text="hello", lang="en")
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    result = stt.transcribe(chunk)
    assert result.text == "hello"
    assert result.language == "en"
    assert result.confidence == 0.9
    assert len(stt.called_with) == 1


def test_fake_stt_preserves_timestamps() -> None:
    stt: SpeechPort = FakeSTT()
    chunk = AudioChunk(
        source=AudioSource.SYSTEM,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=500,
        ended_ns=1_500_000_000,
    )
    result = stt.transcribe(chunk)
    assert result.start_ns == 500
    assert result.end_ns == 1_500_000_000


def test_speech_segment_named_tuple() -> None:
    s = SpeechSegment(text="hi", language="en", start_ns=0, end_ns=1_000_000_000)
    assert s.text == "hi"
    assert s.confidence is None


def test_speech_segment_with_confidence() -> None:
    s = SpeechSegment(text="hi", language="en", start_ns=0, end_ns=1_000_000_000, confidence=0.95)
    assert s.confidence == 0.95
    assert s.start_ns == 0
    assert s.end_ns == 1_000_000_000
~~~

Valide:

~~~powershell
python -m pytest tests/test_speech.py -q
~~~

### M03.3 Meça antes de otimizar

Path: docs/lab/measure_stt.py
~~~python
import time

import numpy as np
import soundcard as sc

from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.adapters.whisper_stt import WhisperSTT

DURATION = 5
SAMPLE_RATE = 16000

mic = sc.default_microphone()
frames = mic.record(samplerate=SAMPLE_RATE, numframes=SAMPLE_RATE * DURATION)
audio = (np.int16(frames[:, 0] * 32767)).tobytes()

chunk = AudioChunk(
    source=AudioSource.MICROPHONE,
    samples=audio,
    sample_rate=SAMPLE_RATE,
    channels=1,
    started_ns=0,
    ended_ns=DURATION * 1_000_000_000,
)

stt = WhisperSTT(model_size="tiny", device="cpu")
t0 = time.perf_counter()
result = stt.transcribe(chunk)
elapsed = time.perf_counter() - t0

rtf = elapsed / DURATION
print(f"Audio: {DURATION}s, Inferência: {elapsed:.2f}s, RTF: {rtf:.2f}")
print(f"Texto: {result.text}")
print(f"Idioma: {result.language}, Confiança: {result.confidence}")
print("RTF < 1.0 significa tempo real; acima disso o modelo não acompanha.")
~~~

Se RTF > 1, troque para modelo `tiny` ou ative GPU com `device="cuda"`.

### M03.4 Conecte transcript ao overlay

Path: src/live_caption_bridge/services/pipeline.py
~~~python
from live_caption_bridge.domain.models import AudioChunk, Caption
from live_caption_bridge.ports.caption_sink import CaptionSink
from live_caption_bridge.ports.speech import SpeechPort


class Pipeline:
    def __init__(self, stt: SpeechPort, sink: CaptionSink, source_lang: str = "pt") -> None:
        self._stt = stt
        self._sink = sink
        self._source_lang = source_lang

    def process(self, chunk: AudioChunk) -> None:
        seg = self._stt.transcribe(chunk)
        if not seg.text:
            return
        caption = Caption(
            original=seg.text,
            translated=seg.text,
            source_lang=seg.language or self._source_lang,
            target_lang=seg.language or self._source_lang,
            started_ns=seg.start_ns,
            ended_ns=seg.end_ns,
        )
        self._sink.publish(caption)
~~~

Path: tests/test_pipeline.py
~~~python
from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.ports.speech import SpeechSegment
from live_caption_bridge.services.pipeline import Pipeline
from tests.fakes import FakeCaptionSink


class FakeSTT:
    def transcribe(self, chunk: AudioChunk) -> SpeechSegment:
        return SpeechSegment(
            text="hello world",
            language="en",
            start_ns=chunk.started_ns,
            end_ns=chunk.ended_ns,
            confidence=0.9,
        )


def test_pipeline_delivers_caption_to_sink() -> None:
    sink = FakeCaptionSink()
    stt = FakeSTT()
    p = Pipeline(stt=stt, sink=sink)
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    p.process(chunk)
    assert sink.last is not None
    assert sink.last.original == "hello world"


def test_pipeline_skips_empty_text() -> None:
    sink = FakeCaptionSink()
    stt = FakeSTT()
    stt.transcribe = lambda c: SpeechSegment(
        text="", language="en", start_ns=c.started_ns, end_ns=c.ended_ns
    )
    p = Pipeline(stt=stt, sink=sink)
    chunk = AudioChunk(
        source=AudioSource.MICROPHONE,
        samples=b"\x00\x00" * 16000,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=1_000_000_000,
    )
    p.process(chunk)
    assert sink.last is None
~~~

Valide:

~~~powershell
python -m pytest tests/test_pipeline.py -q
~~~

### M03.5 Cubra bordas e finalize o marco

Cubra também duração máxima e pre-roll (já incluídos nos testes de M03.1) e SpeechSegment com/sem confiança (já incluídos em M03.2). Teste primeira sílaba, silêncio longo, música, fala contínua, modelo ausente e fila crescente. Legenda parcial pode atualizar a UI, mas apenas a final entra no histórico.

**Checkpoint M03.** VAD e STT têm testes, o modelo é carregado uma vez, RTF é medido e o overlay continua responsivo. Registre em **docs/lab/M03-stt.md**.

~~~powershell
python -m pytest tests -q
python -m ruff check .
~~~

Leitura: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://opennmt.net/CTranslate2/) e [NumPy](https://numpy.org/doc/stable/user/absolute_beginners.html).

## M04 - Tradução por LLM e persistência

**Ponto de partida.** M03 entrega Transcript, mas ainda não há tradução nem histórico. O caminho seguro é contrato falso, servidor HTTP local, falhas e só então persistência. Isso permite desenvolver sem depender de rede ou de um modelo baixado.

### M04.1 Porta de tradução e provider falso

Path: src/live_caption_bridge/ports/translation.py
~~~python
from typing import Protocol

from live_caption_bridge.domain.models import Caption


class TranslationResult:
    def __init__(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        uncertain: bool = False,
    ) -> None:
        self.text = text
        self.source_lang = source_lang
        self.target_lang = target_lang
        self.uncertain = uncertain


class TranslationPort(Protocol):
    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> TranslationResult: ...
~~~

Path: tests/test_translation.py
~~~python
import pytest

from live_caption_bridge.ports.translation import (
    TranslationPort,
    TranslationResult,
)


class FakeTranslation:
    def __init__(self) -> None:
        self._map: dict[tuple[str, str, str], TranslationResult] = {}

    def add(
        self, text: str, src: str, tgt: str, result: TranslationResult
    ) -> None:
        self._map[(text, src, tgt)] = result

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        key = (text, source_lang, target_lang)
        return self._map.get(
            key,
            TranslationResult(
                text=text,
                source_lang=source_lang,
                target_lang=target_lang,
                uncertain=True,
            ),
        )


def test_fake_translates_en_to_pt() -> None:
    t: TranslationPort = FakeTranslation()
    result = t.translate("hello", "en", "pt")
    assert result.text == "hello"
    assert result.source_lang == "en"
    assert result.target_lang == "pt"
    assert result.uncertain is True


def test_fake_returns_mapped_text() -> None:
    f = FakeTranslation()
    f.add("hello", "en", "pt", TranslationResult("olá", "en", "pt"))
    result = f.translate("hello", "en", "pt")
    assert result.text == "olá"
    assert result.uncertain is False
~~~

Valide:

~~~powershell
python -m pytest tests/test_translation.py -q
~~~

### M04.2 Valide a resposta estruturada

Path: src/live_caption_bridge/ports/translation.py (adicione ao final)
~~~python
class TranslationValidationError(ValueError):
    ...


def validate_result(result: TranslationResult) -> None:
    if not result.text or not result.text.strip():
        raise TranslationValidationError("texto vazio")
    if not result.source_lang or not result.target_lang:
        raise TranslationValidationError("idioma ausente")
    if result.source_lang == result.target_lang:
        raise TranslationValidationError("idioma destino igual à origem")
    if not isinstance(result.uncertain, bool):
        raise TranslationValidationError("uncertain deve ser bool")
~~~

Path: tests/test_translation.py (adicione ao final)
~~~python
from live_caption_bridge.ports.translation import (
    TranslationValidationError,
    validate_result,
)


def test_rejects_empty_text() -> None:
    r = TranslationResult("", "en", "pt")
    with pytest.raises(TranslationValidationError, match="vazio"):
        validate_result(r)


def test_rejects_missing_language() -> None:
    r = TranslationResult("hello", "", "pt")
    with pytest.raises(TranslationValidationError, match="ausente"):
        validate_result(r)


def test_rejects_same_language() -> None:
    r = TranslationResult("hello", "en", "en")
    with pytest.raises(TranslationValidationError, match="igual"):
        validate_result(r)


def test_passes_valid_result() -> None:
    r = TranslationResult("olá", "en", "pt")
    validate_result(r)
~~~

Valide:

~~~powershell
python -m pytest tests/test_translation.py -q
~~~

### M04.3 Cliente HTTP com configuração

Path: src/live_caption_bridge/adapters/llm_translation.py
~~~python
import logging
import os

import httpx

from live_caption_bridge.ports.translation import (
    TranslationPort,
    TranslationResult,
    TranslationValidationError,
    validate_result,
)

logger = logging.getLogger(__name__)


def _build_prompt(text: str, target_lang: str) -> str:
    return (
        f"Translate the following text to {target_lang}. "
        f"Respond ONLY with a JSON object containing "
        f'{{"translated": "<translated text>"}}. Text: {text}'
    )


class LLMTranslation:
    def __init__(
        self,
        url: str | None = None,
        model: str | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self._url = url or os.getenv("LCB_LLM_URL", "http://localhost:11434/api/generate")
        self._model = model or os.getenv("LCB_LLM_MODEL", "qwen3:4b")
        self._timeout = timeout_s
        self._client = httpx.Client(timeout=httpx.Timeout(self._timeout))

    def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> TranslationResult:
        prompt = _build_prompt(text, target_lang)
        payload = {"model": self._model, "prompt": prompt, "stream": False}
        logger.debug("enviando tradução para %s", self._url)
        try:
            resp = self._client.post(self._url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            raw = data.get("response", "")
        except httpx.HTTPStatusError as e:
            logger.warning("erro HTTP %s: %s", e.response.status_code, e)
            return TranslationResult(text, source_lang, target_lang, uncertain=True)
        except (httpx.RequestError, ValueError) as e:
            logger.warning("falha na requisição: %s", e)
            return TranslationResult(text, source_lang, target_lang, uncertain=True)
        import json as _json
        try:
            parsed = _json.loads(raw)
            translated = parsed.get("translated", raw)
        except (_json.JSONDecodeError, TypeError):
            translated = raw.strip()
        if not translated:
            translated = text
        result = TranslationResult(translated, source_lang, target_lang)
        try:
            validate_result(result)
        except TranslationValidationError:
            return TranslationResult(text, source_lang, target_lang, uncertain=True)
        return result
~~~

Path: tests/integration/test_llm_translation.py
~~~python
import pytest
import httpx

from live_caption_bridge.adapters.llm_translation import LLMTranslation


@pytest.fixture
def fake_ollama(httpserver) -> httpx.URL:
    httpserver.expect_ordered_request("/api/generate").respond_with_json(
        {"response": '{"translated": "olá"}'}
    )
    return httpserver.url_for("/api/generate")


def test_translation_against_fake_server(fake_ollama: httpx.URL) -> None:
    t = LLMTranslation(url=str(fake_ollama), model="test", timeout_s=5.0)
    result = t.translate("hello", "en", "pt")
    assert result.text == "olá"
    assert result.uncertain is False


def test_fallback_on_server_error(fake_ollama: httpx.URL) -> None:
    t = LLMTranslation(url=str(fake_ollama) + "/invalid", model="test", timeout_s=5.0)
    result = t.translate("hello", "en", "pt")
    assert result.text == "hello"
    assert result.uncertain is True
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_llm_translation.py -q
~~~

### M04.4 Conecte o Ollama centralizado

Path: docs/lab/ollama_test.py
~~~python
from live_caption_bridge.adapters.llm_translation import LLMTranslation

t = LLMTranslation()
result = t.translate("Hello, how are you?", "en", "pt")
print(f"Tradução: {result.text}")
print(f"Incerteza: {result.uncertain}")
~~~

~~~powershell
python docs/lab/ollama_test.py
~~~

### M04.5 Trate falhas antes do banco

Path: src/live_caption_bridge/adapters/llm_translation.py (adicione retry)
~~~python
import time
from functools import wraps


def _retry(max_attempts: int = 2, delay_s: float = 0.5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 502, 503, 504):
                        last = e
                        if attempt < max_attempts - 1:
                            time.sleep(delay_s * (attempt + 1))
                            continue
                    raise
            raise last
        return wrapper
    return decorator
~~~

Path: tests/integration/test_llm_translation.py (adicione)
~~~python
def test_retry_on_429(fake_ollama: httpx.URL, httpserver) -> None:
    httpserver.expect_ordered_request("/api/generate").respond_with_data(
        status=429
    )
    httpserver.expect_ordered_request("/api/generate").respond_with_json(
        {"response": '{"translated": "olá"}'}
    )
    t = LLMTranslation(url=str(fake_ollama), model="test", timeout_s=5.0)
    result = t.translate("hello", "en", "pt")
    assert result.text == "olá"
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_llm_translation.py -q
~~~

### M04.6 Persista sem depender da rede

Path: src/live_caption_bridge/adapters/sqlite_repository.py
~~~python
import sqlite3
import time
from pathlib import Path


class SQLiteRepository:
    def __init__(self, db_path: str | Path) -> None:
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS captions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original TEXT NOT NULL,
                translated TEXT,
                source_lang TEXT NOT NULL,
                target_lang TEXT,
                started_ns INTEGER NOT NULL,
                ended_ns INTEGER NOT NULL,
                created_ns INTEGER NOT NULL
            )"""
        )
        self._conn.commit()

    def save(
        self,
        original: str,
        translated: str | None,
        source_lang: str,
        target_lang: str | None,
        started_ns: int,
        ended_ns: int,
    ) -> int:
        now = time.monotonic_ns()
        cur = self._conn.execute(
            """INSERT INTO captions
               (original, translated, source_lang, target_lang,
                started_ns, ended_ns, created_ns)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (original, translated, source_lang, target_lang,
             started_ns, ended_ns, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def close(self) -> None:
        self._conn.close()
~~~

Path: tests/integration/test_sqlite_repository.py
~~~python
import tempfile
from pathlib import Path

from live_caption_bridge.adapters.sqlite_repository import SQLiteRepository


def test_save_and_retrieve() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteRepository(Path(tmp) / "test.db")
        row_id = db.save(
            original="hello",
            translated="olá",
            source_lang="en",
            target_lang="pt",
            started_ns=0,
            ended_ns=100,
        )
        assert row_id is not None and row_id > 0
        db.close()


def test_save_original_without_translation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteRepository(Path(tmp) / "test.db")
        row_id = db.save(
            original="hello",
            translated=None,
            source_lang="en",
            target_lang=None,
            started_ns=0,
            ended_ns=100,
        )
        assert row_id is not None
        db.close()
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_sqlite_repository.py -q
~~~

**Checkpoint M04.** URL e modelo mudam somente por configuração, falhas externas são simuláveis e a queda do serviço não perde o original. Registre em **docs/lab/M04-llm.md**.

~~~powershell
python -m pytest tests -q
~~~

Leitura: [HTTPX](https://www.python-httpx.org/), [JSON Schema](https://json-schema.org/learn/getting-started-step-by-step), [SQLite](https://www.sqlite.org/lang.html) e a documentação do provider escolhido.

## M05 - Loopback e identidade das fontes

**Ponto de partida.** M04 funciona com uma fonte. Agora adicionaremos o áudio do sistema sem misturá-lo com o microfone. A regra é reutilizar AudioChunk e o mesmo worker; somente a seleção da fonte muda.

### M05.1 Enumere endpoints loopback

Path: src/live_caption_bridge/ports/audio.py (adicione ao final)
~~~python
from enum import StrEnum


class DeviceKind(StrEnum):
    MICROPHONE = "microphone"
    SPEAKER = "speaker"
~~~

Path: src/live_caption_bridge/ports/audio.py (altere AudioDeviceInfo)
~~~python
class AudioDeviceInfo:
    def __init__(self, name: str, id: str, kind: DeviceKind = DeviceKind.MICROPHONE) -> None:
        self.name = name
        self.id = id
        self.kind = kind
~~~

Path: tests/test_loopback_enumeration.py
~~~python
from live_caption_bridge.ports.audio import AudioDeviceInfo, DeviceKind


class FakeLoopbackEnumerator:
    def list_devices(self) -> list[AudioDeviceInfo]:
        return [
            AudioDeviceInfo("Microphone (Realtek)", "mic1", DeviceKind.MICROPHONE),
            AudioDeviceInfo("Speakers (Realtek)", "spk1", DeviceKind.SPEAKER),
        ]


def test_enumerator_distinguishes_mic_and_speaker() -> None:
    enum = FakeLoopbackEnumerator()
    devices = enum.list_devices()
    mics = [d for d in devices if d.kind == DeviceKind.MICROPHONE]
    spk = [d for d in devices if d.kind == DeviceKind.SPEAKER]
    assert len(mics) == 1
    assert len(spk) == 1
    assert mics[0].id == "mic1"
    assert spk[0].id == "spk1"
~~~

Valide:

~~~powershell
python -m pytest tests/test_loopback_enumeration.py -q
~~~

### M05.2 Reutilize o worker

Path: src/live_caption_bridge/services/audio_workers.py
~~~python
import queue
import threading
from collections.abc import Callable

from live_caption_bridge.domain.models import AudioChunk, AudioSource


class AudioWorker:
    def __init__(
        self,
        source: AudioSource,
        read_chunk: Callable[[], AudioChunk],
        maxsize: int = 10,
    ) -> None:
        self._source = source
        self._read = read_chunk
        self._queue: queue.Queue = queue.Queue(maxsize=maxsize)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        def _run() -> None:
            while not self._stop.is_set():
                try:
                    chunk = self._read()
                    self._queue.put(chunk, timeout=0.1)
                except queue.Full:
                    continue
                except Exception:
                    if not self._stop.is_set():
                        raise
        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def read(self) -> AudioChunk | None:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None
~~~

Path: tests/test_audio_workers.py
~~~python
from live_caption_bridge.domain.models import AudioChunk, AudioSource
from live_caption_bridge.services.audio_workers import AudioWorker


def _make_chunk(source: AudioSource) -> AudioChunk:
    return AudioChunk(
        source=source,
        samples=b"\x00\x00" * 1600,
        sample_rate=16000,
        channels=1,
        started_ns=0,
        ended_ns=100_000_000,
    )


def test_worker_delivers_chunk_with_correct_source() -> None:
    worker = AudioWorker(
        source=AudioSource.SYSTEM,
        read_chunk=lambda: _make_chunk(AudioSource.SYSTEM),
    )
    worker.start()
    import time
    time.sleep(0.05)
    worker.stop()
    chunk = worker.read()
    assert chunk is not None
    assert chunk.source == AudioSource.SYSTEM


def test_two_workers_produce_separate_sources() -> None:
    mic = AudioWorker(
        source=AudioSource.MICROPHONE,
        read_chunk=lambda: _make_chunk(AudioSource.MICROPHONE),
    )
    sys = AudioWorker(
        source=AudioSource.SYSTEM,
        read_chunk=lambda: _make_chunk(AudioSource.SYSTEM),
    )
    mic.start()
    sys.start()
    import time
    time.sleep(0.05)
    mic.stop()
    sys.stop()
    mc = mic.read()
    sc = sys.read()
    assert mc is not None and mc.source == AudioSource.MICROPHONE
    assert sc is not None and sc.source == AudioSource.SYSTEM
~~~

Valide:

~~~powershell
python -m pytest tests/test_audio_workers.py -q
~~~

### M05.3 Prove as fontes separadamente

Path: docs/lab/capture_loopback.py
~~~python
import wave

import numpy as np
import soundcard as sc

SAMPLE_RATE = 16000
DURATION = 5

for kind, func in [("mic", sc.default_microphone), ("speaker", sc.default_speaker)]:
    mic = func()
    frames = mic.record(samplerate=SAMPLE_RATE, numframes=SAMPLE_RATE * DURATION)
    audio = (np.int16(frames[:, 0] * 32767)).tobytes()
    path = f"docs/lab/capture_{kind}.wav"
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio)
    print(f"Salvo {path}")
~~~

### M05.4 Teste simultaneidade e limitações

Troque Bluetooth, remova um dispositivo, use Remote Desktop e verifique DRM. Se o microfone recapturar o alto-falante, registre a limitação e recomende headset; AEC não entra neste marco porque introduziria outra cadeia de processamento.

**Checkpoint M05.** Cada fonte mantém identidade constante, os WAVs tocam isoladamente e a falha de uma fonte não derruba a outra. Registre em **docs/lab/M05-loopback.md**.

~~~powershell
python -m pytest -m "not audio_device" -q
~~~

Leitura: [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording), [Core Audio](https://learn.microsoft.com/en-us/windows/win32/coreaudio/core-audio-apis-in-windows-vista) e [SoundCard](https://soundcard.readthedocs.io/en/latest/).

## M06 - Replay de vídeo sem áudio

**Ponto de partida.** M05 fornece áudio identificado, mas ainda não há replay. Primeiro resolveremos captura, memória e timestamps somente para vídeo; mux de áudio ficaria mais difícil de diagnosticar se fosse introduzido agora.

### M06.1 Porta de gravação e frame único

Path: src/live_caption_bridge/ports/recorder.py
~~~python
from typing import Protocol


class ScreenFrame:
    def __init__(self, rgba: bytes, width: int, height: int, pts_ns: int) -> None:
        self.rgba = rgba
        self.width = width
        self.height = height
        self.pts_ns = pts_ns


class RecorderPort(Protocol):
    def capture_frame(self) -> ScreenFrame: ...
    def close(self) -> None: ...
~~~

Path: src/live_caption_bridge/adapters/ffmpeg_recorder.py
~~~python
import subprocess
import tempfile
from pathlib import Path
from typing import IO

import mss


def capture_one_frame() -> dict:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        frame = sct.grab(monitor)
        return {
            "width": frame.width,
            "height": frame.height,
            "pixel_format": "BGRA",
            "monitor": monitor,
        }


if __name__ == "__main__":
    info = capture_one_frame()
    print(f"Monitor: {info['monitor']}")
    print(f"Tamanho: {info['width']}x{info['height']}, Formato: {info['pixel_format']}")
~~~

Teste manual:

~~~powershell
python -m live_caption_bridge.adapters.ffmpeg_recorder
~~~

### M06.2 Segmento comprimido de dois segundos

Path: src/live_caption_bridge/adapters/ffmpeg_recorder.py (adicione)
~~~python
import subprocess
import tempfile
from pathlib import Path


def _ffmpeg_encode(
    frames: list[bytes],
    width: int,
    height: int,
    output_path: str | Path,
    fps: int = 15,
) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{width}x{height}",
        "-pix_fmt", "bgra",
        "-r", str(fps),
        "-i", "-",
        "-an",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "23",
        str(output_path),
    ]
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for frame in frames:
        proc.stdin.write(frame)
    proc.stdin.close()
    proc.wait()


def encode_segment(
    frames: list[bytes], width: int, height: int, output: str | Path, fps: int = 15
) -> None:
    _ffmpeg_encode(frames, width, height, output, fps)
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
         str(output)],
        capture_output=True, text=True,
    )
    duration = result.stdout.strip()
    print(f"Segmento salvo: {output}, duração: {duration}s")
~~~

Valide com ffprobe:

~~~powershell
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 segment.mp4
~~~

### M06.3 Ring temporal

Path: src/live_caption_bridge/services/replay_service.py
~~~python
import os
import tempfile
import threading
from pathlib import Path
from collections.abc import Callable


class ReplayService:
    def __init__(
        self,
        max_duration_s: int = 120,
        segment_duration_s: int = 2,
        temp_dir: str | Path | None = None,
    ) -> None:
        self._max_segments = max_duration_s // segment_duration_s
        self._seg_dur = segment_duration_s
        self._temp_dir = Path(temp_dir or tempfile.gettempdir()) / "lcb_replay"
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def save_window(
        self,
        segments: list[Path],
        output: str | Path,
        encode_fn: Callable[[list[Path], str | Path], None],
    ) -> None:
        with self._lock:
            encode_fn(segments, output)

    def prune(self, segments: list[Path]) -> list[Path]:
        with self._lock:
            while len(segments) > self._max_segments:
                old = segments.pop(0)
                if old.exists():
                    os.remove(old)
            return segments
~~~

Path: tests/integration/test_replay_service.py
~~~python
from live_caption_bridge.services.replay_service import ReplayService


def test_prune_removes_excess_segments() -> None:
    svc = ReplayService(max_duration_s=6, segment_duration_s=2)
    segments = [f"seg{i}.mp4" for i in range(5)]
    import pathlib
    for s in segments:
        pathlib.Path(s).write_text("fake")
    try:
        remaining = svc.prune(segments)
        assert len(remaining) <= 3
    finally:
        for s in segments:
            p = pathlib.Path(s)
            if p.exists():
                p.unlink()
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_replay_service.py -q
~~~

### M06.4 Salve uma janela atomicamente

Path: src/live_caption_bridge/services/replay_service.py (adicione)
~~~python
import subprocess
import shutil


def concat_segments(
    segment_paths: list[Path],
    output: str | Path,
) -> None:
    tmp = Path(str(output) + ".tmp.mp4")
    list_path = Path(str(output) + ".list.txt")
    try:
        with open(list_path, "w") as f:
            for seg in segment_paths:
                f.write(f"file '{seg.resolve()}'\n")
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration", "-of",
             "default=noprint_wrappers=1:nokey=1",
             str(segment_paths[0])],
            capture_output=True, text=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
             "-i", str(list_path),
             "-c", "copy", str(tmp)],
            check=True, capture_output=True,
        )
        shutil.move(str(tmp), str(output))
    finally:
        if tmp.exists():
            tmp.unlink()
        if list_path.exists():
            list_path.unlink()
~~~

### M06.5 Teste concorrência

Path: tests/integration/test_replay_service.py (adicione)
~~~python
import threading
import tempfile
from pathlib import Path

from live_caption_bridge.services.replay_service import ReplayService


def test_concurrent_saves_do_not_collide() -> None:
    svc = ReplayService(max_duration_s=30, segment_duration_s=2)
    results: list[Exception | None] = [None, None]
    lock = threading.Lock()

    def fake_encode(segments: list[Path], out: str | Path) -> None:
        Path(out).write_text("ok")

    def save(idx: int) -> None:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / f"out{idx}.mp4"
                svc.save_window([], out, fake_encode)
        except Exception as e:
            results[idx] = e

    t1 = threading.Thread(target=save, args=(0,))
    t2 = threading.Thread(target=save, args=(1,))
    t1.start()
    t2.start()
    t1.join(timeout=5)
    t2.join(timeout=5)
    assert all(r is None for r in results)
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_replay_service.py -q
~~~

**Checkpoint M06.** RAM estabiliza, ffprobe confirma vídeo e duração, dois saves são reproduzíveis e o arquivo abre em um player Windows. Registre em **docs/lab/M06-replay-video.md**.

~~~powershell
ffmpeg -version
ffprobe -version
python -m pytest -m "not desktop_capture" -q
~~~

Leitura: [FFmpeg](https://ffmpeg.org/ffmpeg.html), [formatos](https://ffmpeg.org/ffmpeg-formats.html), [mss](https://python-mss.readthedocs.io/) e [subprocess](https://docs.python.org/3/library/subprocess.html).

## M07 - Replay com trilhas separadas e sincronia

**Ponto de partida.** M06 salva vídeo. Agora adicionaremos sistema e microfone como streams separadas; não trataremos canais estéreo como se fossem fontes distintas.

### M07.1 Congele três janelas temporais

Path: src/live_caption_bridge/services/replay_service.py (adicione RingWindow)
~~~python
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RingWindow:
    video_segments: list[Path]
    mic_segments: list[Path]
    sys_segments: list[Path]
    start_ns: int
    end_ns: int
~~~

Path: tests/test_replay_window.py
~~~python
from pathlib import Path

from live_caption_bridge.services.replay_service import RingWindow


def test_ring_window_preserves_gaps() -> None:
    w = RingWindow(
        video_segments=[Path("vid1.mp4"), Path("vid2.mp4")],
        mic_segments=[Path("mic1.mp4")],
        sys_segments=[],
        start_ns=0,
        end_ns=4_000_000_000,
    )
    assert len(w.video_segments) == 2
    assert len(w.mic_segments) == 1
    assert len(w.sys_segments) == 0
    assert w.end_ns - w.start_ns == 4_000_000_000
~~~

Valide:

~~~powershell
python -m pytest tests/test_replay_window.py -q
~~~

### M07.2 Muxe somente o sistema

Path: src/live_caption_bridge/adapters/ffmpeg_recorder.py (adicione)
~~~python
def mux_video_audio(
    video_path: str | Path,
    audio_path: str | Path | None,
    output: str | Path,
    audio_title: str = "System",
) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    if audio_path:
        cmd += ["-i", str(audio_path)]
        cmd += ["-c:v", "copy", "-c:a", "aac"]
        cmd += ["-metadata:s:a:0", f"title={audio_title}"]
        cmd += ["-map", "0:v:0", "-map", "1:a:0"]
    else:
        cmd += ["-c:v", "copy"]
    cmd.append(str(output))
    subprocess.run(cmd, check=True, capture_output=True)


def ffprobe_streams(path: str | Path) -> list[dict]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams",
         "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    import json
    data = json.loads(result.stdout)
    return data.get("streams", [])
~~~

Valide manualmente com:

~~~powershell
ffprobe -v error -show_streams -show_format replay.mp4
~~~

### M07.3 Adicione o microfone

Path: src/live_caption_bridge/adapters/ffmpeg_recorder.py (adicione)
~~~python
def mux_three_tracks(
    video: str | Path,
    mic_audio: str | Path | None,
    sys_audio: str | Path | None,
    output: str | Path,
) -> None:
    cmd = ["ffmpeg", "-y", "-i", str(video)]
    inputs = [video]
    maps = ["-map", "0:v:0"]
    if mic_audio:
        cmd += ["-i", str(mic_audio)]
        maps += ["-map", f"{len(inputs)}:a:0"]
        inputs.append(mic_audio)
    if sys_audio:
        cmd += ["-i", str(sys_audio)]
        maps += ["-map", f"{len(inputs)}:a:0"]
        inputs.append(sys_audio)
    cmd += ["-c:v", "copy", "-c:a", "aac"]
    track_idx = 0
    if mic_audio:
        cmd += ["-metadata:s:a:" + str(track_idx), "title=Mic"]
        track_idx += 1
    if sys_audio:
        cmd += ["-metadata:s:a:" + str(track_idx), "title=System"]
    cmd += maps
    cmd.append(str(output))
    subprocess.run(cmd, check=True, capture_output=True)
~~~

Teste com fontes ausentes (simula falha):

Path: tests/integration/test_replay_service.py (adicione)
~~~python
def test_mux_with_missing_mic_falls_back() -> None:
    from live_caption_bridge.adapters.ffmpeg_recorder import mux_three_tracks
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        vid = Path(tmp) / "vid.mp4"
        out = Path(tmp) / "out.mp4"
        vid.write_text("fake")
        # Sem audio — só vídeo, não deve lançar
        mux_three_tracks(vid, None, None, out)
        assert out.exists()
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_replay_service.py -q
~~~

### M07.4 Defina a faixa padrão e meça drift

Path: docs/lab/measure_drift.py
~~~python
import time
from live_caption_bridge.adapters.ffmpeg_recorder import ffprobe_streams

path = "replay.mp4"
streams = ffprobe_streams(path)
for s in streams:
    print(
        f"  #{s['index']} {s.get('codec_type')} "
        f"codec={s.get('codec_name')} "
        f"title={s.get('tags', {}).get('title', '')} "
        f"dur={s.get('duration')}s"
    )

# Drift: toque 30s e meça diferença PTS vs relógio
t0 = time.monotonic()
# (reprodução real ou leitura de PTS com ffprobe)
print("Meça drift comparando PTS final com duração esperada")
~~~

**Checkpoint M07.** ffprobe prova títulos e índices, cada faixa toca isoladamente e drift fica abaixo da meta com gaps, mute e início tardio. Registre em **docs/lab/M07-replay-audio.md**.

~~~powershell
ffprobe -v error -show_streams -show_format replay.mp4
python -m pytest -m "not audio_device and not desktop_capture" -q
~~~

Leitura: [seleção de streams](https://ffmpeg.org/ffmpeg.html#Stream-selection), [disposition](https://ffmpeg.org/ffmpeg.html#Advanced-options) e [ffprobe](https://ffmpeg.org/ffprobe.html).

## M08 - Produto resiliente

**Ponto de partida.** M07 funciona no caminho feliz. Este marco transforma falhas, recursos e privacidade em comportamento observável. A sequência começa por configuração e ciclo de vida porque hotkeys e degradação precisam de um processo que saiba iniciar e parar componentes.

### M08.1 Centralize configurações

Path: src/live_caption_bridge/infrastructure/settings.py
~~~python
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "LCB_"}

    llm_url: str = "http://localhost:11434/api/generate"
    llm_model: str = "qwen3:4b"
    sample_rate: int = 16000
    channels: int = 1
    replay_seconds: int = 120
    data_dir: Path = Path.home() / ".live_caption_bridge"

    def validate_settings(self) -> None:
        if self.sample_rate not in (8000, 16000, 44100, 48000):
            raise ValueError(f"sample_rate inválido: {self.sample_rate}")
        if self.channels < 1 or self.channels > 2:
            raise ValueError(f"channels inválido: {self.channels}")
        if self.replay_seconds < 10 or self.replay_seconds > 600:
            raise ValueError(f"replay_seconds deve estar entre 10 e 600")
~~~

Path: tests/test_settings.py
~~~python
from live_caption_bridge.infrastructure.settings import Settings


def test_default_values() -> None:
    s = Settings()
    assert s.sample_rate == 16000
    assert s.replay_seconds == 120
    assert s.channels == 1


def test_rejects_invalid_sample_rate() -> None:
    s = Settings(sample_rate=12345)
    import pytest
    with pytest.raises(ValueError):
        s.validate_settings()
~~~

Valide:

~~~powershell
python -m pytest tests/test_settings.py -q
~~~

### M08.2 Torne o encerramento explícito

Path: src/live_caption_bridge/infrastructure/lifecycle.py
~~~python
from collections.abc import Callable


class Lifecycle:
    def __init__(self) -> None:
        self._startups: list[Callable[[], None]] = []
        self._shutdowns: list[Callable[[], None]] = []

    def on_start(self, fn: Callable[[], None]) -> None:
        self._startups.append(fn)

    def on_shutdown(self, fn: Callable[[], None]) -> None:
        self._shutdowns.insert(0, fn)

    def start(self) -> None:
        errors: list[Exception] = []
        for fn in self._startups:
            try:
                fn()
            except Exception as e:
                errors.append(e)
        if errors:
            self.shutdown()
            raise RuntimeError(f"startup falhou: {errors}")

    def shutdown(self) -> None:
        for fn in self._shutdowns:
            try:
                fn()
            except Exception:
                pass
~~~

Path: tests/test_lifecycle.py
~~~python
from live_caption_bridge.infrastructure.lifecycle import Lifecycle


def test_startup_and_shutdown_order() -> None:
    order: list[str] = []
    lc = Lifecycle()
    lc.on_start(lambda: order.append("start"))
    lc.on_shutdown(lambda: order.append("shutdown"))
    lc.start()
    lc.shutdown()
    assert order == ["start", "shutdown"]


def test_startup_failure_triggers_shutdown() -> None:
    lc = Lifecycle()
    lc.on_start(lambda: exec("raise RuntimeError('fail')"))
    called = False
    lc.on_shutdown(lambda: nonlocal_func())  # noqa
    # Na prática on_shutdown chama cleanup
    import pytest
    with pytest.raises(RuntimeError):
        lc.start()
~~~

Valide:

~~~powershell
python -m pytest tests/test_lifecycle.py -q
~~~

### M08.3 Hotkeys reais (Windows)

Path: src/live_caption_bridge/adapters/windows_hotkeys.py
~~~python
import ctypes
from ctypes import wintypes

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_NOREPEAT = 0x4000

_user32 = ctypes.windll.user32


class WindowsHotKey:
    def __init__(self) -> None:
        self._next_id = 1

    def register(self, mod: int, vk: int) -> int:
        hwnd = None
        fid = self._next_id
        if not _user32.RegisterHotKey(hwnd, fid, mod, vk):
            raise RuntimeError(f"RegisterHotKey falhou para id {fid}")
        self._next_id += 1
        return fid

    def unregister(self, id: int) -> None:
        hwnd = None
        _user32.UnregisterHotKey(hwnd, id)

    @staticmethod
    def listen(timeout_ms: int = 100) -> int | None:
        msg = wintypes.MSG()
        result = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if result == 0:
            return None
        if msg.message == WM_HOTKEY:
            return msg.wParam
        _user32.TranslateMessage(ctypes.byref(msg))
        _user32.DispatchMessageW(ctypes.byref(msg))
        return None
~~~

Path: tests/e2e/test_hotkeys.py
~~~python
import pytest

pytestmark = pytest.mark.hotkey


def test_register_and_unregister_does_not_raise() -> None:
    from live_caption_bridge.adapters.windows_hotkeys import WindowsHotKey
    hk = WindowsHotKey()
    fid = hk.register(0, 0x70)  # F1 sem mod
    hk.unregister(fid)
~~~

Execute no Windows nativo:

~~~powershell
python -m pytest tests/e2e/test_hotkeys.py -m hotkey -q
~~~

### M08.4 Meça e degrade uma coisa por vez

Path: src/live_caption_bridge/services/resource_governor.py
~~~python
import time
from collections.abc import Callable


class ResourceGovernor:
    def __init__(
        self,
        queue_max: int = 50,
        check_interval_s: float = 2.0,
    ) -> None:
        self._queue_max = queue_max
        self._interval = check_interval_s
        self._last_check = 0.0
        self._fps_reduced = False
        self._callbacks: list[Callable[[str], None]] = []

    def on_degradation(self, cb: Callable[[str], None]) -> None:
        self._callbacks.append(cb)

    def check(self, queue_size: int) -> None:
        now = time.monotonic()
        if now - self._last_check < self._interval:
            return
        self._last_check = now
        if queue_size > self._queue_max and not self._fps_reduced:
            self._fps_reduced = True
            for cb in self._callbacks:
                cb("fps_reduced")

    def reset(self) -> None:
        self._fps_reduced = False
~~~

Path: tests/test_resource_governor.py
~~~python
from live_caption_bridge.services.resource_governor import ResourceGovernor


def test_degradation_triggers_on_high_queue() -> None:
    g = ResourceGovernor(queue_max=5, check_interval_s=0)
    actions: list[str] = []
    g.on_degradation(lambda msg: actions.append(msg))
    g.check(10)
    assert "fps_reduced" in actions


def test_no_degradation_when_queue_below_limit() -> None:
    g = ResourceGovernor(queue_max=5, check_interval_s=0)
    actions: list[str] = []
    g.on_degradation(lambda msg: actions.append(msg))
    g.check(3)
    assert len(actions) == 0
~~~

Valide:

~~~powershell
python -m pytest tests/test_resource_governor.py -q
~~~

### M08.5 Proteja dados e injete falhas

Path: tests/integration/test_failure_recovery.py
~~~python
import tempfile
from pathlib import Path

import pytest


def test_database_survives_service_offline() -> None:
    from live_caption_bridge.adapters.sqlite_repository import SQLiteRepository
    with tempfile.TemporaryDirectory() as tmp:
        db = SQLiteRepository(Path(tmp) / "test.db")
        db.save("original", None, "en", None, 0, 100)
        db.close()
        db2 = SQLiteRepository(Path(tmp) / "test.db")
        row_id = db2.save("novo", "new", "pt", "en", 200, 300)
        assert row_id is not None
        db2.close()


def test_recovery_after_abrupt_restart() -> None:
    from live_caption_bridge.adapters.sqlite_repository import SQLiteRepository
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "test.db"
        db = SQLiteRepository(p)
        db.save("antes", "before", "pt", "en", 0, 100)
        db.close()
        db2 = SQLiteRepository(p)
        row_id = db2.save("depois", "after", "pt", "en", 200, 300)
        assert row_id is not None
        db2.close()
~~~

Valide:

~~~powershell
python -m pytest tests/integration/test_failure_recovery.py -q
~~~

**Checkpoint M08.** A UI permanece responsiva, falhas injetadas deixam dados válidos, captura é visível e degradação é comunicada antes da perda. Registre em **docs/lab/M08-resiliencia.md**.

~~~powershell
python -m pytest tests -q
python -m mypy src
~~~

Leitura: [RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey), [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/), [logging](https://docs.python.org/3/howto/logging.html) e [psutil](https://psutil.readthedocs.io/en/latest/).

## M09 - Qualidade, empacotamento e release

**Ponto de partida.** M08 entrega comportamento resiliente, mas ainda não prova que outra máquina conseguirá instalar e reproduzir o fluxo. Este marco transforma os testes de laboratório em uma release auditável.

### M09.1 Congele a matriz de qualidade

Liste testes unitários, integração portátil, Qt headless, Windows/hardware e E2E. Marque explicitamente windows, audio_device, desktop_capture e hotkey; o contêiner executa apenas os testes portáveis, enquanto Windows executa os demais.

Registre os markers no **pyproject.toml** (na seção de configuração do pytest) e
aplique-os no topo dos testes que exigem o recurso, por exemplo
`pytestmark = pytest.mark.audio_device`. O marker não pula um teste silenciosamente:
ele documenta por que aquele teste precisa ser executado no Windows nativo.

### M09.2 Reproduza a imagem e o venv

Construa a imagem Docker documentada e rode nela pytest, Ruff, mypy e ffprobe. Repita os testes portáveis no venv Windows. A mesma configuração de dependências detecta diferenças de plataforma sem fingir que Docker fornece WASAPI ou GPU.

### M09.3 Empacote no Windows nativo

Gere o executável com PyInstaller, inclua plugins Qt e DLLs realmente necessários e teste em uma VM Windows limpa. O Docker continua sendo ferramenta de desenvolvimento e CI; não é interface de distribuição e não substitui o instalador Windows.

### M09.4 Faça o E2E final

Suba o servidor LLM local ou centralizado, valide URL configurada, capture microfone, loopback, overlay, hotkey, tela, GPU e replay. Registre latência, drift, falhas e licenças de FFmpeg. O marco termina quando outra pessoa repete o roteiro pelo README.

**Checkpoint M09.** Build limpo, testes portáveis reproduzíveis em Docker e venv, testes de hardware aprovados no Windows e instalador validado.

Execute os três comandos portáveis na imagem documentada e repita-os no venv Windows:

~~~powershell
docker compose run --rm dev pytest -m "not windows and not audio_device and not desktop_capture and not hotkey"
docker compose run --rm dev ruff check .
docker compose run --rm dev mypy src
~~~

Leitura: [PyInstaller](https://pyinstaller.org/en/stable/), [profiling Python](https://docs.python.org/3/library/profile.html), [licenças FFmpeg](https://ffmpeg.org/legal.html) e [Python Packaging User Guide](https://packaging.python.org/).

## M10 - Beta orientado por evidência

**Ponto de partida.** M09 prova a release em ambiente controlado. O beta deve revelar diferenças de hardware sem transformar relatos vagos em decisões arquiteturais.

### M10.1 Prepare observação segura

Crie um template de bug com versão, passos, hardware, logs sanitizados e resultado esperado. Telemetria é somente opt-in e nunca inclui áudio, vídeo, prompts ou texto capturado; métricas agregadas bastam para identificar gargalos.

### M10.2 Comece com um grupo pequeno

Escolha máquinas que representem microfone, loopback, múltiplos monitores, DPI, GPU e Remote Desktop. Entregue o mesmo instalador e o mesmo roteiro, porque mudanças de procedimento confundem diferenças reais do produto.

### M10.3 Converta incidentes em evidência

Classifique severidade, reproduza em laboratório e transforme cada falha em teste, limitação documentada ou correção. Não marque um problema como resolvido apenas porque deixou de aparecer uma vez; a repetição controlada é a unidade de conhecimento.

**Checkpoint M10.** Cada incidente tem caso reproduzível, teste ou limitação visível, e o changelog explica incompatibilidades conhecidas. Só então a versão pode ser considerada beta orientado por evidência.

Antes de distribuir, repita a matriz sem os marcadores de hardware e arquive o resultado junto do changelog:

~~~powershell
python -m pytest -m "not windows and not audio_device and not desktop_capture and not hotkey" -q
~~~

Em todos os marcos, avance somente quando conseguir demonstrar, testar, explicar e diagnosticar o componente no hardware alvo. A existência de arquivos não é evidência de funcionamento.

## Referencias tecnicas

A partir daqui ficam reunidos contratos, exemplos e detalhes de componentes usados
pelos marcos. Consulte uma subseção somente quando o passo do marco correspondente a
pedir; nao crie toda esta estrutura antecipadamente.

### 5. Contratos entre camadas (Protocols)

Os modelos de dados (AudioSource, AudioChunk, Transcript, Caption) foram criados
passo a passo no M01. Eles carregam apenas dados, sem comportamento. As fronteiras
entre camadas são definidas por `Protocol`s:

```python
from typing import Protocol

from live_caption_bridge.domain.models import Caption, AudioChunk


class CaptionSink(Protocol):
    def publish(self, caption: Caption) -> None: ...


class AudioSourcePort(Protocol):
    def list_devices(self) -> list[dict]: ...
    def open(self, device_id: str) -> None: ...
    def read_chunk(self) -> AudioChunk: ...
    def close(self) -> None: ...
```

Cada Protocol declara timeout, cancelamento e erros recuperaveis. Isso evita que
uma falha externa vire congelamento da UI.

Audio de microfone e audio do sistema continuam identificados desde a captura ate
o arquivo final. Nunca use um unico buffer como fonte canonica. Se for preciso
oferecer uma mixagem, derive-a das duas fontes e mantenha os originais.

Use `time.monotonic_ns()` para ordenar e sincronizar eventos durante a sessao.
Armazene tambem um timestamp UTC para historico, mas nunca sincronize A/V com o
relogio de parede, pois ele pode mudar.

### 6. Configuracao e segredos

Comece com uma unica configuracao carregada em memoria e um teste para o valor
padrao. Depois leia uma variavel `LCB_` do ambiente e teste a validacao de limite.
So quando o aplicativo realmente precisar de credencial, conecte `keyring`. Por
ultimo, adicione migracao e configuracoes de usuario; nao crie um sistema completo
de preferencias antes de existir uma segunda opcao configuravel.

Modele configuracoes como dados validados:

Path: src/live_caption_bridge/infrastructure/settings.py
```python
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LCB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    locale: str = "pt-BR"
    whisper_model: str = "small"
    replay_seconds: int = Field(default=30, ge=5, le=300)
    capture_fps: int = Field(default=20, ge=5, le=60)
    max_memory_percent: int = Field(default=70, ge=40, le=90)
    data_dir: Path = Path.home() / ".live-caption-bridge"
    translation_base_url: str = "http://127.0.0.1:11434/v1"
    translation_model: str | None = None
    translation_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
```

O prefixo `LCB_` separa configuracoes do aplicativo das demais variaveis do sistema.
`env_file` faz o aplicativo ler a mesma configuracao local usada pelo Compose;
`extra="ignore"` permite que chaves exclusivas do Ollama coexistam no arquivo sem
virarem erro de validacao. Variaveis reais do processo continuam tendo precedencia
sobre o `.env`, o que permite overrides controlados em teste ou implantacao.
Os limites de replay, FPS, memoria e timeout rejeitam configuracoes perigosas antes
de iniciar workers. `data_dir` centraliza dados locais; `translation_base_url`
desacopla o cliente do servidor Docker; e `translation_model=None` obriga o primeiro
uso a escolher conscientemente um modelo em vez de baixar um artefato grande sem
consentimento.

Descubra o idioma padrao a partir do Windows no primeiro uso, mas permita alterar.
Guarde chaves em Windows Credential Manager via `keyring`, nunca em JSON ou log.

### 7. Captura de audio

O primeiro resultado desta etapa e enumerar dispositivos e gravar cinco segundos de
uma unica fonte em WAV. Quando o arquivo abrir e seus timestamps forem conferidos,
extraia a captura para uma porta e um adaptador. Apenas depois introduza um worker,
fila limitada e reabertura com backoff. Essa ordem separa formato PCM de problemas
de concorrencia e de hardware.

#### 7.1 Enumeracao e selecao

Liste microfones e loopbacks, salve identificadores estaveis e ofereca teste de
nivel antes de confirmar. Dispositivo default pode mudar entre reinicios.

Com SoundCard, o loopback costuma aparecer como microfone criado a partir do
speaker. Valide no seu equipamento e trate lista vazia como estado de configuracao,
nao como excecao fatal.

#### 7.2 Workers

Use um worker por fonte. Cada worker:

1. abre o dispositivo;
2. captura blocos curtos, por exemplo 20 a 100 ms;
3. converte para mono/16 kHz no adaptador de STT quando necessario;
4. marca inicio e fim com relogio monotonic;
5. publica em uma fila limitada;
6. tenta reabrir com backoff se o dispositivo desaparecer.

Nunca capture no thread do Qt. Uma fila sem limite transforma atraso do modelo em
consumo ilimitado de RAM. Quando cheia, descarte audio antigo ainda nao processado
ou agregue blocos conforme uma politica explicita e incremente uma metrica.

### 8. Segmentacao e VAD

Comece com um WAV conhecido e uma funcao que separa fala e silencio. Teste pre-roll,
silencio final e duracao maxima sem envolver microfone ao vivo. Depois conecte a
funcao ao worker de audio e, por ultimo, ajuste limiares com ruido real. Cada
alteracao deve preservar os timestamps que o STT consumira.

Nao envie cada bloco diretamente ao Whisper. Monte segmentos usando VAD:

- mantenha um pequeno pre-roll para nao cortar a primeira silaba;
- encerre o segmento apos silencio configuravel;
- limite a duracao maxima para controlar latencia;
- preserve os timestamps originais;
- separe microfone e sistema para nao misturar falantes indevidamente.

O faster-whisper oferece filtro VAD e timestamps. Ainda assim, teste conversas
curtas, fala continua, musica, silencio e ruido. Uma legenda parcial pode ser
atualizada, mas apenas a final entra no historico permanente.

### 9. STT com faster-whisper

Use primeiro um arquivo WAV curto e um modelo pequeno para provar que o adaptador
retorna texto e idioma. Depois meca o real-time factor e memoria; so entao carregue
o modelo uma vez no processo de longa duracao. A etapa final e substituir o arquivo
por segmentos do VAD, preservando o mesmo contrato e os mesmos testes de latencia.

Carregue uma unica instancia do modelo por processo:

Path: src/live_caption_bridge/adapters/whisper_stt.py
```python
from faster_whisper import WhisperModel

class WhisperSpeechRecognizer:
    def __init__(self, model_name: str, device: str = "cpu") -> None:
        compute_type = "int8" if device == "cpu" else "float16"
        self._model = WhisperModel(model_name, device=device,
                                   compute_type=compute_type)

    def transcribe(self, wav_path: str):
        segments, info = self._model.transcribe(
            wav_path,
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, info.language
```

Uma instancia unica evita duplicar o modelo na RAM ou VRAM. `int8` reduz memoria e
custo em CPU; `float16` aproveita GPUs compativeis. `beam_size=5` busca alternativas
para ganhar qualidade, enquanto VAD evita inferencia sobre silencio e timestamps de
palavra preservam sincronizacao. Esses valores sao ponto de partida: benchmark de
latencia e acuracia decide se devem mudar no hardware alvo.

No produto, evite arquivos temporarios por segmento: adapte arrays NumPy ou um
buffer WAV em memoria. O exemplo acima serve primeiro para comprovar o modelo.

Meca `real-time factor = tempo de inferencia / duracao do audio`. Para legendas
ao vivo ele precisa ficar abaixo de 1 de forma sustentada, idealmente com folga.

### 10. Traducao com LLM

Implemente primeiro um provider falso que devolve uma traducao deterministica. Em
seguida valide o JSON e os erros contra esse falso; depois conecte Ollama ou outro
endpoint OpenAI-compatible por HTTP. Por fim acrescente timeout, retry, circuit
breaker e fallback para o original. O servidor real entra depois que o contrato ja
pode ser testado sem rede.

#### 10.1 Regra linguistica

- fala detectada como ingles: traduzir para o idioma configurado;
- qualquer outro idioma: traduzir para ingles;
- nomes, numeros, URLs e termos tecnicos devem ser preservados;
- se a deteccao estiver incerta, use contexto recente ou marque a incerteza.

#### 10.2 Contrato estruturado

Nao aceite explicacoes livres do modelo. Exija JSON validado:

```json
{
  "translation": "texto traduzido",
  "source_lang": "en",
  "target_lang": "pt-BR",
  "uncertain": false
}
```

`translation` contem apenas o resultado; idiomas de origem e destino permitem
auditar a regra linguistica; e `uncertain` torna duvida um dado observavel em vez de
esconde-la. O schema reduz ambiguidades, mas ainda precisa de validacao porque um
modelo pode produzir JSON sintaticamente valido com valores semanticamente errados.

System prompt sugerido:

```text
You are a real-time translation component. Translate only the supplied speech.
Preserve names, numbers, paths, URLs and technical terms. Return valid JSON that
matches the provided schema. Never add commentary or answer the speaker.
```

O prompt limita o modelo a traduzir, preserva tokens tecnicos e proibe comentarios.
Isso reduz respostas inventadas e mantem a saida adequada ao overlay; nao substitui
schema, timeout nem testes, pois instrucao textual nao e uma garantia de execucao.

Implemente um `TranslationProvider` com adaptadores para um modelo local e para
um endpoint OpenAI-compatible. Configure timeouts curtos, retry apenas para falhas
transitorias e circuit breaker. Cacheie traducoes por hash de texto, idiomas e
versao do prompt. Nao envie audio ao LLM; envie somente texto necessario.

Para latencia, mantenha uma janela curta de contexto e traduza frases finais. Se
o provider estiver lento, mostre a transcricao original e atualize a traducao
depois, sem bloquear captura ou UI.

### 11. Pipeline concorrente e backpressure

Monte inicialmente uma pipeline sequencial com uma entrada conhecida, para provar a
ordem captura -> VAD -> STT -> traducao -> persistencia. Depois transforme apenas a
fronteira mais lenta em uma fila limitada e meca a diferenca. Acrescente workers,
cancelamento e supervisao um por vez; assim uma fila crescente nao fica escondida
por varias camadas novas introduzidas simultaneamente.

Use esta topologia:

```text
Mic worker ----\
                -> VAD/segmentos -> STT -> traducao -> UI + SQLite
Loopback worker-/          \
                            -> ring de audio do replay

Captura de tela -----------------> ring de video do replay
```

Na implementacao, existem tres rings temporais independentes: video, microfone e
sistema. Eles compartilham a mesma origem monotonic, mas podem ter formatos e
taxas diferentes. O servico de replay seleciona a mesma janela temporal nos tres
e o muxer cria streams separados; nao confunda "dois canais estereo" com "duas
trilhas de audio". Canais pertencem a uma stream; aqui precisamos de duas streams.

Regras essenciais:

- Qt main thread: somente widgets e sinais curtos;
- workers de captura: prioridade e trabalho minimo;
- um worker STT por modelo/GPU, salvo benchmark que prove concorrencia;
- fila de traducao limitada, com cancelamento de parciais obsoletas;
- escritor SQLite unico e transacoes curtas;
- cancelamento cooperativo por `threading.Event`;
- supervisao que reinicia somente o adaptador falho;
- encerramento ordenado: parar entrada, drenar o necessario, persistir, fechar.

Registre p50/p95 de cada etapa e profundidade das filas. Sem essas metricas, voce
nao sabera se a lentidao esta na captura, STT, traducao ou renderizacao.

### 12. Overlay PySide6

Primeiro mostre uma janela fixa com texto estatico. Depois faça o texto chegar por um
sinal usando uma fonte falsa; em seguida ajuste transparencia, posicionamento e
DPI. O modo click-through e a integracao com a pipeline so entram quando a janela
simples puder ser aberta, atualizada e fechada sem bloquear o thread Qt.

O overlay deve ser frameless, translucido e sempre no topo. As flags Qt relevantes
incluem `FramelessWindowHint`, `WindowStaysOnTopHint` e, no modo click-through,
`WindowTransparentForInput`. Ative `WA_TranslucentBackground`.

Path: src/live_caption_bridge/ui/overlay.py
```python
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout

class CaptionOverlay(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.label = QLabel()
        self.label.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)

    def set_click_through(self, enabled: bool) -> None:
        flags = self.windowFlags()
        flag = Qt.WindowTransparentForInput
        self.setWindowFlags(flags | flag if enabled else flags & ~flag)
        self.show()
```

`QWidget` fornece uma janela leve; `QLabel` renderiza texto com quebra de linha; e
`QVBoxLayout` controla margens e redimensionamento. As flags removem moldura, mantem
o overlay acima e evitam um item comum na barra de tarefas. O metodo click-through
altera somente a recepcao de input e chama `show()` porque trocar flags pode recriar
a janela nativa no Windows.

Adicione fundo com contraste ajustavel, tamanho da fonte, largura maxima, margens
seguras, monitor escolhido e posicao. Teste 100%, 125%, 150% e 200% de DPI, varios
monitores, tela cheia e aplicativos com privilegio elevado.

### 13. Historico e configuracoes

Comece criando apenas a tabela de legendas e inserindo uma linha em uma transacao.
Depois implemente busca temporal e filtro por fonte; em seguida retencao e
exportacao. Exclusao, limpeza e recuperacao de processo interrompido entram depois
que o caminho feliz de leitura e escrita estiver coberto por testes.

Use SQLite em modo WAL. Tabelas minimas:

```sql
CREATE TABLE captions (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    source TEXT NOT NULL,
    original TEXT NOT NULL,
    translated TEXT NOT NULL,
    source_lang TEXT NOT NULL,
    target_lang TEXT NOT NULL,
    started_utc TEXT NOT NULL,
    ended_utc TEXT NOT NULL
);
CREATE INDEX idx_captions_started ON captions(started_utc);
```

Uma linha representa uma legenda final, ligada a sessao e fonte para permitir
filtros sem perder autoria. Original e traducao ficam separados para reprocessar ou
exportar depois. O indice temporal acelera historico e selecao da janela de replay;
nao crie indices adicionais antes de medir, pois cada indice aumenta custo de escrita.

Ofereca busca, filtro por sessao/fonte/idioma, exportacao SRT/JSON e exclusao. A
politica de retencao deve ser configuravel. O usuario precisa poder desativar o
historico e limpar audio, video e texto pelo aplicativo.

### 14. Gravacao dos segundos anteriores

Divida o replay em experimentos independentes: primeiro salve somente video por uma
janela curta; depois adicione a trilha de sistema; em seguida a de microfone; por
fim remuxe, nomeie streams e sincronize. Cada etapa deve produzir um arquivo que
`ffprobe` e um player consigam abrir antes da proxima fonte ser acrescentada.

#### 14.0 Requisito de produto: faixas de audio separadas

Todo video gerado deve preservar, quando disponiveis:

| Stream | Titulo no container | Conteudo | Obrigatoria |
| --- | --- | --- | --- |
| Video | `Screen` | tela capturada | sim |
| Audio 1 | `System audio` | o que o usuario esta ouvindo via loopback | se ativo |
| Audio 2 | `Microphone` | o que o usuario esta falando | se ativo |
| Audio 3 | `Mixed` | mixagem derivada para conveniencia | nao, opt-in |

O microfone nao deve ser somado ao loopback antes da persistencia. Cada fonte tem
seu proprio encoder AAC, PTS, fila, metrica de perda e controle de ganho/mute. O
player pode escolher uma trilha; um editor pode mixar depois. Como muitos players
tocam apenas a faixa marcada como default, deixe `Mixed` como default quando ela
existir; sem ela, escolha uma das originais e explique na UI como trocar a faixa.

Se o microfone captar fisicamente o som dos alto-falantes, a separacao logica nao
remove eco. Para o primeiro MVP, recomende headset e detecte niveis correlacionados;
AEC e uma etapa futura, medida e opcional, pois pode degradar a voz original.

#### 14.1 Nao use frames brutos sem limite

Uma tela 1920x1080 RGB a 30 fps ultrapassa 180 MB por segundo sem compressao.
Portanto, nao mantenha o replay como uma lista de screenshots em RAM.

#### 14.2 Arquitetura recomendada

Capture tela e audio com timestamps monotonic e alimente um encoder continuo que
gere pequenos segmentos comprimidos, por exemplo de dois segundos, em um diretorio
temporario no mesmo disco do destino. Mantenha apenas os segmentos necessarios
para `replay_seconds` mais uma margem.

Ao pressionar a hotkey:

1. marque atomicamente o instante de corte;
2. congele a lista de segmentos que cobre a janela solicitada;
3. finalize o segmento corrente;
4. concatene/remuxe para um arquivo temporario;
5. valide com `ffprobe` a presenca de video, audio, duracao e timestamps;
6. renomeie atomicamente para `.mp4`;
7. gere `.srt` e `.json` com as legendas da mesma janela;
8. libere segmentos antigos apenas quando nenhum save os estiver usando.

O mux final deve mapear streams explicitamente. Um experimento didatico, partindo
de video, audio do sistema e microfone ja alinhados, e:

```powershell
ffmpeg -i video.mp4 -i system.wav -i microphone.wav `
  -map 0:v:0 -map 1:a:0 -map 2:a:0 -c:v copy -c:a aac `
  -metadata:s:a:0 title="System audio" `
  -metadata:s:a:1 title="Microphone" `
  -disposition:a:0 default -disposition:a:1 0 output.mp4
```

Este comando e um laboratorio, nao o encoder continuo final. A ordem de `-map`
define os indices das trilhas de saida. Na aplicacao, passe argumentos como lista
ao `subprocess`, nunca como uma string montada. Valide que existem duas streams de
audio distintas, nao apenas que `codec_type=audio` aparece alguma vez.

O encoder pode ser um adaptador baseado em FFmpeg ou PyAV. Comece com H.264 e
AAC, mas descubra encoders de hardware disponiveis e use fallback para software.
Nao assuma que NVENC, Quick Sync ou AMF existe.

#### 14.3 Sincronizacao A/V

Escolha o inicio da sessao monotonic como origem comum. Audio e video carregam PTS
derivados desse relogio. Nao sincronize por contagem de frames, pois frames podem
ser descartados. Se houver drift, ajuste no mux/encoder de forma mensurada e
registre o valor.

Valide cada arquivo:

```powershell
ffprobe -v error -show_entries format=duration `
  -show_entries stream=index,codec_type,codec_name,start_time,duration:stream_tags=title `
  -of json .\recordings\sample.mp4
```

Um arquivo existente nao e prova: reproduza-o, confira audio, imagem, duracao,
sincronia e abertura em um player instalado no Windows.

### 15. Atalhos globais

Registre primeiro uma unica hotkey que apenas escreve um log. Depois encaminhe o
evento para um comando de replay falso; so entao conecte o gravador e trate conflitos
ou reconfiguracao. O handler nunca deve começar com encoding real, porque isso
misturaria o loop de mensagens com I/O longo.

Use a API Win32 `RegisterHotKey` em um adaptador e encaminhe `WM_HOTKEY` para um
sinal Qt. Permita reconfiguracao e detecte conflito antes de salvar. O handler so
enfileira o comando de save; encoding e I/O nunca rodam no loop de mensagens.

Defina atalhos separados para:

- salvar replay recente;
- mostrar/ocultar overlay;
- pausar captura;
- ativar/desativar click-through.

Explique claramente quando um atalho nao puder ser registrado por outro app.

### 16. Governor de recursos

Comece observando CPU, memoria, filas e disco sem alterar comportamento. Depois
adicione um unico limite e uma degradacao visivel, como reduzir FPS; em seguida
encadeie resolucao, traducao e pausa do replay. Cada politica precisa de um teste
que prove a transicao e de uma mensagem curta para o usuario.

Colete CPU, RAM disponivel, GPU quando observavel, profundidade das filas, espaco
em disco e tempo de inferencia. Aplique degradacao gradual:

1. reduzir FPS da captura;
2. reduzir resolucao do replay;
3. aumentar intervalo de legendas parciais;
4. diminuir concorrencia de traducao;
5. trocar modelo STT somente se o usuario permitir;
6. pausar replay antes de comprometer captura e interface.

Reserve memoria para o Windows e pare a gravacao antes de esgotar disco. Mostre um
estado curto ao usuario e preserve logs tecnicos sem dados privados.

### 17. Privacidade e seguranca

Implemente primeiro consentimento e indicador persistente de captura. Depois limite
arquivos temporarios e limpe-os no encerramento; em seguida remova segredos dos logs
e valide paths. So depois documente provider remoto, retencao e exclusao completa.
Essas protecoes acompanham cada nova fonte de dado, em vez de serem adiadas para o
fim do projeto.

- Exiba consentimento claro antes da primeira captura.
- Mostre indicador persistente enquanto microfone, sistema ou tela estiver ativo.
- Nao salve audio ou video por padrao fora do ring temporario.
- Apague segmentos temporarios no encerramento e na proxima inicializacao.
- Restrinja permissoes do diretorio de dados ao usuario atual.
- Saneie nomes de arquivo e nunca monte comandos FFmpeg com strings concatenadas.
- Use lista de argumentos em subprocessos e valide paths resolvidos.
- Remova texto e segredos de logs; use IDs e metricas agregadas.
- Documente quando dados forem enviados a um provider remoto.

Gravacao pode envolver consentimento legal de terceiros. A aplicacao deve tornar
a captura visivel e oferecer retencao curta; o usuario continua responsavel pelas
leis aplicaveis ao local e ao contexto.

### 18. Estrategia de testes

Aumente a cobertura na mesma ordem em que o produto cresce: unidade para cada regra,
integracao para cada adaptador real, E2E para o fluxo completo e soak para detectar
problemas que so aparecem com tempo. Cada marco deve adicionar primeiro o teste que
falha com a nova capacidade e depois a implementacao que o faz passar.

#### 18.1 Unitarios

Cubra regras linguisticas, segmentacao, ring temporal, retencao, conversao de PTS,
cache, configuracoes e recuperacao. Eles evitam regressao, mas nao provam hardware.

#### 18.2 Integracao

- WAVs reais com idiomas, ruido e silencio para STT;
- provider local/remoto com schema valido, timeout e resposta malformada;
- SQLite com concorrencia, migracao e recuperacao de processo interrompido;
- FFmpeg/ffprobe com clips reais e duracoes diferentes;
- hotkey registrada e liberada em processo Windows de teste.

Suba o servidor Docker separadamente e rode os testes pelo Windows contra sua API.
Cubra instancia local e centralizada, modelo ausente, indisponibilidade, timeout,
resposta fora do schema e recuperacao sem reiniciar captura ou interface.

#### 18.3 E2E em hardware real

Execute, registre evidencias e repita apos empacotar:

| Cenario | Resultado esperado |
| --- | --- |
| Microfone em portugues | Legenda em ingles, historico correto |
| Microfone em ingles | Legenda no idioma configurado |
| Video no navegador | Loopback transcrito sem realimentar o microfone |
| Duas fontes simultaneas | UI responsiva e fontes identificaveis |
| Dispositivo removido | Recuperacao ou selecao guiada, sem crash |
| Provider offline | Original continua; traducao recupera depois |
| Hotkey em outro app | Replay salvo sem roubar foco |
| Replay de 30 e 120 s | MP4 reproduzivel, A/V sincronizado e duracao correta |
| Replay com duas fontes | Duas trilhas nomeadas; cada uma toca isoladamente |
| Apenas uma fonte ativa | Exporta sem falhar e sem fabricar trilha silenciosa |
| Microfone mutado no meio | Trilha e timestamps continuam validos |
| Dois monitores/DPI | Overlay inteiro, reposicionado e sem bloquear cliques |
| Pressao de RAM/CPU | Degradacao gradual, desktop ainda utilizavel |
| Disco quase cheio | Captura interrompida com seguranca, sem arquivo corrompido |
| Reinicio abrupto | Banco integro e temporarios recuperados/removidos |

#### 18.4 Soak e desempenho

Rode por pelo menos duas horas com audio alternando entre fala e silencio. Observe
vazamento de memoria, handles, crescimento de fila, drift A/V e tamanho do cache.
Depois rode oito horas como gate de release.

Metas iniciais, ajustadas pelo seu hardware:

- UI sem bloqueio acima de 100 ms;
- latencia fala-legenda p95 abaixo de 2 s em hardware alvo;
- traducao p95 abaixo de 1,5 s ou fallback visivel para original;
- drift A/V abaixo de 100 ms em replay de dois minutos;
- memoria estabilizada, sem crescimento continuo no soak;
- zero perda silenciosa de historico ou replay;
- inicializacao fria abaixo de 10 s, excluindo primeiro download explicito.

### 19. Empacotamento e entrega

Empacote somente depois que o comando de desenvolvimento estiver estavel. Primeiro
gere um executavel que inicia; depois inclua plugins Qt e DLLs observados; em seguida
valide FFmpeg, modelos e dados em uma VM limpa. O instalador, assinatura e upgrade
so entram quando o executavel isolado ja puder ser diagnosticado.

1. Fixe dependencias e licencas em `pyproject.toml`/lockfile.
2. Baixe modelos somente com consentimento, progresso, espaco prevalidado e destino
   configuravel; nao use `C:` implicitamente para artefatos grandes.
3. Crie um spec PyInstaller que inclua plugins Qt e DLLs realmente necessarios.
4. Distribua FFmpeg apenas se a licenca e a build escolhida permitirem; caso
   contrario, detecte uma instalacao suportada.
5. Assine executavel e instalador para uma distribuicao publica.
6. Teste em uma VM Windows limpa, sem Python, Git ou cache de desenvolvimento.
7. Verifique instalar, primeiro uso, upgrade preservando dados e desinstalar.
8. Publique checksums, notas de privacidade, requisitos e procedimento de suporte.

O container de LLM e um servico auxiliar, nao o produto. O instalador Windows nao
deve embutir Docker nem assumir que o servidor esta na mesma maquina; primeiro uso
deve aceitar uma URL local ou centralizada e testar a conexao antes de salva-la.

## Critérios para qualidade satisfatória

Considere a primeira versao satisfatoria somente quando:

- todos os cenarios E2E da tabela estiverem aprovados no executavel empacotado;
- STT e traducao atingirem as metas de latencia e qualidade em amostra diversa;
- replay MP4 abrir em players distintos e mantiver sincronia;
- overlay funcionar em multiplos monitores, DPI e tela cheia;
- hotkeys, historico, retencao e recuperacao forem previsiveis;
- soak nao revelar crescimento continuo de memoria, handles, disco ou filas;
- nenhum segredo ou captura privada aparecer em logs;
- uma instalacao limpa puder ser feita por outra pessoa seguindo o README;
- o servidor Docker reiniciar sem perder modelos e o aplicativo degradar com
  seguranca quando a instancia local ou centralizada estiver indisponivel;
- limitacoes conhecidas estiverem visiveis e nao forem apresentadas como sucesso.

## Fontes técnicas adicionais

- Qt for Python, flags de janela: <https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html>
- Qt for Python, widgets e translucidez: <https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html>
- SoundCard e dispositivos de audio: <https://soundcard.readthedocs.io/en/latest/>
- faster-whisper: <https://github.com/SYSTRAN/faster-whisper>
- Ollama em Docker: <https://docs.ollama.com/docker>
- Compatibilidade OpenAI do Ollama: <https://docs.ollama.com/api/openai-compatibility>
- Variaveis e `.env` no Docker Compose: <https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/>
- Qwen3 no catalogo Ollama: <https://ollama.com/library/qwen3>
- pip-tools e pip-compile: <https://pip-tools.readthedocs.io/en/stable/>
- FFmpeg FAQ: <https://ffmpeg.org/faq.html>
- FFmpeg Filters/Formats/Devices: <https://ffmpeg.org/documentation.html>

Consulte sempre a documentacao da versao fixada no projeto. APIs, compatibilidade
de hardware e dependencias de runtime podem mudar.
