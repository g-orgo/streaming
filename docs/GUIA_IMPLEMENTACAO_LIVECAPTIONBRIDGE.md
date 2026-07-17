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
pip install PySide6 soundcard numpy faster-whisper mss pydantic-settings `
  psutil httpx keyring pytest pytest-qt ruff mypy
```

O bloco cria uma pasta, entra nela, isola as dependencias em `.venv`, ativa esse
ambiente, atualiza o instalador de pacotes e so entao instala a stack. O isolamento
evita misturar versoes deste projeto com outros programas Python do computador.

Cada dependencia tem uma responsabilidade deliberada:

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

No M00, crie `infra/llm/compose.yaml` seguindo este modelo:

```yaml
services:
  translation-llm:
    image: ollama/ollama:latest
    restart: unless-stopped
    ports:
      - "127.0.0.1:11434:11434"
    volumes:
      - ollama-models:/root/.ollama

volumes:
  ollama-models:
```

O servico recebe o nome `translation-llm` para expressar sua unica funcao. A imagem
fornece o servidor; `restart` recupera o processo apos reinicio; o bind em
`127.0.0.1` impede acesso externo acidental; e o volume guarda modelos fora do
ciclo de vida do container, evitando downloads a cada inicializacao.

Durante o laboratorio inicial, `latest` reduz atrito. Antes de compartilhar o
ambiente ou liberar uma versao, substitua-o por uma tag ou digest testado e registre
a escolha em ADR. Inicie o servidor, baixe conscientemente um modelo de traducao e
valide a API:

```powershell
$modelName = "substitua-pelo-modelo-escolhido"
docker compose -f .\infra\llm\compose.yaml up -d
docker compose -f .\infra\llm\compose.yaml exec translation-llm `
  ollama pull $modelName
Invoke-RestMethod http://127.0.0.1:11434/api/tags
docker compose -f .\infra\llm\compose.yaml logs --tail 100 translation-llm
```

`up -d` inicia em segundo plano; `exec ... pull` baixa o modelo dentro do servico;
`Invoke-RestMethod` confirma que a API responde; e `logs` mostra a causa observavel
caso a inicializacao ou descoberta de hardware falhe. Executar essas verificacoes
separadamente distingue problema de infraestrutura de problema no aplicativo.

Nao fixe o nome do modelo antes do benchmark do M04. Registre tamanho, licenca,
idiomas testados, RAM/VRAM, latencia p95 e qualidade; entao configure o cliente:

```text
LCB_TRANSLATION_BASE_URL=http://127.0.0.1:11434/v1
LCB_TRANSLATION_API_KEY=ollama
LCB_TRANSLATION_MODEL=<modelo-escolhido>
```

`BASE_URL` permite trocar uma instancia local por uma central sem alterar codigo;
`API_KEY` uniformiza o contrato do cliente; e `MODEL` torna explicita a versao de
inferencia que afeta qualidade, latencia e cache.

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

### 3.2 Como usar este guia para realmente aprender

Este projeto nao deve virar uma colecao de codigo copiado da LLM. Em cada marco,
use o ciclo abaixo ate conseguir explicar o resultado sem consultar o chat:

Regra editorial deste guia: nenhuma biblioteca, comando, bloco de codigo ou decisao
arquitetural deve aparecer apenas como receita. O texto deve explicar o problema
resolvido, por que a escolha foi feita, como as partes se conectam e qual limite ou
risco precisa ser validado. Se essa justificativa estiver ausente, complete a
documentacao antes de implementar.

1. **Leia o minimo indicado:** entenda os conceitos e anote as duvidas.
2. **Escreva uma hipotese:** descreva entradas, saidas, falhas e como testar.
3. **Implemente pequeno:** faca a menor demonstracao que atravessa a fronteira.
4. **Teste e observe:** guarde comando, saida relevante e metrica em `docs/lab/`.
5. **Quebre de proposito:** simule timeout, dispositivo ausente e dado invalido.
6. **Explique de volta:** registre em poucas linhas por que funciona e seus limites.
7. **So entao integre:** conecte ao proximo componente por uma interface testada.

Para cada marco, crie `docs/lab/MXX-nome.md` com: objetivo, conceitos, desenho,
comandos executados, evidencia, falhas encontradas, decisao e proximo passo. O
Git deve receber um commit pequeno e executavel por marco. Se voce nao consegue
reverter, reproduzir e explicar o commit, o marco ainda nao terminou.

### 3.3 Como usar uma LLM sem terceirizar seu entendimento

Use a LLM como par de engenharia, nao como autoridade. Forneca sempre versoes,
sistema operacional, trecho minimo, resultado esperado, resultado real e log
completo do erro (removendo segredos). Bons pedidos:

```text
Explique este erro a partir da primeira causa observavel. Liste tres hipoteses em
ordem, uma verificacao barata para cada uma e nao proponha mudanca antes do teste.
```

```text
Revise este patch procurando concorrencia, perda de dados, cancelamento e testes
ausentes. Cite a linha e proponha o menor teste que reproduz cada risco.
```

```text
Quero aprender este codigo. Primeiro descreva o fluxo e as invariantes; depois me
faca tres perguntas. Nao reescreva a solucao ate eu responder.
```

Antes de aceitar uma resposta: consulte a documentacao da versao instalada,
reproduza em um exemplo minimo, adicione um teste de regressao e registre por que
a alteracao resolve a causa. Nunca cole comandos destrutivos, chaves ou dados de
captura em um prompt. A LLM ajuda a formar hipoteses; logs, testes e documentacao
decidem se a hipotese e verdadeira.

Os tres exemplos tem propositos diferentes: o primeiro organiza diagnostico sem
chutar correcoes; o segundo procura riscos concretos em um patch; e o terceiro usa
perguntas para verificar entendimento antes de entregar outra solucao pronta.

### 3.4 Ferramentas basicas que voce deve dominar

- ambiente virtual, imports, excecoes, context managers, dataclasses e typing;
- Git: `status`, `diff`, commits pequenos, branches e `bisect` para regressao;
- `pytest`, fixtures, doubles/fakes e diferenca entre teste unitario e integracao;
- logging estruturado, debugger, profiler e leitura de stack trace;
- processos, threads, filas limitadas, timeout, cancelamento e backpressure;
- formatos PCM/WAV, sample rate, canais, codec, container, PTS e mux;
- SQL e transacoes; HTTP, JSON Schema, retry e idempotencia.

Nao e preciso dominar tudo antes de comecar. O plano da secao 20 introduz cada
assunto quando ele passa a ser necessario.

### 3.5 Protocolo para resolver perrengues

Quando algo falhar, nao altere varias coisas ao mesmo tempo:

1. preserve o erro completo, versoes, configuracao e horario;
2. reduza para a menor entrada que ainda falha;
3. identifique a fronteira: hardware, captura, fila, modelo, rede, banco, mux ou UI;
4. compare uma execucao boa e uma ruim usando logs e metricas da mesma fronteira;
5. formule hipoteses falsificaveis e teste primeiro a mais barata;
6. corrija a causa, escreva o teste de regressao e reverta experimentos laterais;
7. documente sintoma, causa, verificacao e solucao em `docs/troubleshooting.md`.

Comece por `python --version`, `python -m pip --version`, `ffmpeg -version`, espaco
em disco, dispositivos enumerados e configuracao efetiva sem segredos. Depois
verifique profundidade das filas, timestamps e a primeira excecao; mensagens
posteriores costumam ser consequencia. Use `git bisect` quando uma versao antiga
funciona e a atual nao. Uma solucao so esta confirmada quando o caso minimo falha
antes, passa depois e o comportamento principal continua coberto.

## 4. Estrutura do projeto

```text
StreamingProject/
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
      0001-template.md
    lab/
      M00-fundacao.md
  src/live_caption_bridge/
    __init__.py
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

`domain` nao importa Qt, SoundCard, Whisper ou FFmpeg. `ports` define protocolos;
`adapters` trata bibliotecas externas; `services` coordena casos de uso; `ui` roda
no thread principal. Essa fronteira permite testar e substituir componentes.

## 5. Modelos e contratos

Comece pelos dados que atravessam a pipeline:

```python
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

@dataclass(frozen=True, slots=True)
class Transcript:
    source: AudioSource
    text: str
    language: str
    started_ns: int
    ended_ns: int
    confidence: float | None = None

@dataclass(frozen=True, slots=True)
class Caption:
    original: str
    translated: str
    source_language: str
    target_language: str
    started_ns: int
    ended_ns: int
```

`AudioSource` evita representar origem com strings livres. `AudioChunk` transporta
PCM e tempo sem conhecer SoundCard; `Transcript` representa o resultado do STT; e
`Caption` separa original de traducao para que uma falha externa nunca apague o que
foi reconhecido. `frozen=True` impede alteracao acidental durante a pipeline e
`slots=True` reduz memoria, importante porque muitos eventos ficam em transito.

Audio de microfone e audio do sistema continuam identificados desde a captura ate
o arquivo final. Nunca use um unico buffer como fonte canonica. Se for preciso
oferecer uma mixagem para reproducao rapida, derive-a das duas fontes e mantenha
os originais.

Use `time.monotonic_ns()` para ordenar e sincronizar eventos durante a sessao.
Armazene tambem um timestamp UTC para historico, mas nunca sincronize A/V com o
relogio de parede, pois ele pode mudar.

Defina `Protocol`s para captura, STT, traducao, repositorio e gravador. Cada metodo
deve declarar timeout, cancelamento e erros recuperaveis. Isso evita que uma falha
externa vire congelamento da UI.

## 6. Configuracao e segredos

Modele configuracoes como dados validados:

```python
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LCB_")

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
Os limites de replay, FPS, memoria e timeout rejeitam configuracoes perigosas antes
de iniciar workers. `data_dir` centraliza dados locais; `translation_base_url`
desacopla o cliente do servidor Docker; e `translation_model=None` obriga o primeiro
uso a escolher conscientemente um modelo em vez de baixar um artefato grande sem
consentimento.

Descubra o idioma padrao a partir do Windows no primeiro uso, mas permita alterar.
Guarde chaves em Windows Credential Manager via `keyring`, nunca em JSON ou log.

## 7. Captura de audio

### 7.1 Enumeracao e selecao

Liste microfones e loopbacks, salve identificadores estaveis e ofereca teste de
nivel antes de confirmar. Dispositivo default pode mudar entre reinicios.

Com SoundCard, o loopback costuma aparecer como microfone criado a partir do
speaker. Valide no seu equipamento e trate lista vazia como estado de configuracao,
nao como excecao fatal.

### 7.2 Workers

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

## 8. Segmentacao e VAD

Nao envie cada bloco diretamente ao Whisper. Monte segmentos usando VAD:

- mantenha um pequeno pre-roll para nao cortar a primeira silaba;
- encerre o segmento apos silencio configuravel;
- limite a duracao maxima para controlar latencia;
- preserve os timestamps originais;
- separe microfone e sistema para nao misturar falantes indevidamente.

O faster-whisper oferece filtro VAD e timestamps. Ainda assim, teste conversas
curtas, fala continua, musica, silencio e ruido. Uma legenda parcial pode ser
atualizada, mas apenas a final entra no historico permanente.

## 9. STT com faster-whisper

Carregue uma unica instancia do modelo por processo:

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

## 10. Traducao com LLM

### 10.1 Regra linguistica

- fala detectada como ingles: traduzir para o idioma configurado;
- qualquer outro idioma: traduzir para ingles;
- nomes, numeros, URLs e termos tecnicos devem ser preservados;
- se a deteccao estiver incerta, use contexto recente ou marque a incerteza.

### 10.2 Contrato estruturado

Nao aceite explicacoes livres do modelo. Exija JSON validado:

```json
{
  "translation": "texto traduzido",
  "source_language": "en",
  "target_language": "pt-BR",
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

## 11. Pipeline concorrente e backpressure

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

## 12. Overlay PySide6

O overlay deve ser frameless, translucido e sempre no topo. As flags Qt relevantes
incluem `FramelessWindowHint`, `WindowStaysOnTopHint` e, no modo click-through,
`WindowTransparentForInput`. Ative `WA_TranslucentBackground`.

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

## 13. Historico e configuracoes

Use SQLite em modo WAL. Tabelas minimas:

```sql
CREATE TABLE captions (
    id INTEGER PRIMARY KEY,
    session_id TEXT NOT NULL,
    source TEXT NOT NULL,
    original TEXT NOT NULL,
    translated TEXT NOT NULL,
    source_language TEXT NOT NULL,
    target_language TEXT NOT NULL,
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

## 14. Gravacao dos segundos anteriores

### 14.0 Requisito de produto: faixas de audio separadas

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

### 14.1 Nao use frames brutos sem limite

Uma tela 1920x1080 RGB a 30 fps ultrapassa 180 MB por segundo sem compressao.
Portanto, nao mantenha o replay como uma lista de screenshots em RAM.

### 14.2 Arquitetura recomendada

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

### 14.3 Sincronizacao A/V

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

## 15. Atalhos globais

Use a API Win32 `RegisterHotKey` em um adaptador e encaminhe `WM_HOTKEY` para um
sinal Qt. Permita reconfiguracao e detecte conflito antes de salvar. O handler so
enfileira o comando de save; encoding e I/O nunca rodam no loop de mensagens.

Defina atalhos separados para:

- salvar replay recente;
- mostrar/ocultar overlay;
- pausar captura;
- ativar/desativar click-through.

Explique claramente quando um atalho nao puder ser registrado por outro app.

## 16. Governor de recursos

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

## 17. Privacidade e seguranca

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

## 18. Estrategia de testes

### 18.1 Unitarios

Cubra regras linguisticas, segmentacao, ring temporal, retencao, conversao de PTS,
cache, configuracoes e recuperacao. Eles evitam regressao, mas nao provam hardware.

### 18.2 Integracao

- WAVs reais com idiomas, ruido e silencio para STT;
- provider local/remoto com schema valido, timeout e resposta malformada;
- SQLite com concorrencia, migracao e recuperacao de processo interrompido;
- FFmpeg/ffprobe com clips reais e duracoes diferentes;
- hotkey registrada e liberada em processo Windows de teste.

Suba o servidor Docker separadamente e rode os testes pelo Windows contra sua API.
Cubra instancia local e centralizada, modelo ausente, indisponibilidade, timeout,
resposta fora do schema e recuperacao sem reiniciar captura ou interface.

### 18.3 E2E em hardware real

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

### 18.4 Soak e desempenho

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

## 19. Empacotamento e entrega

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

## 20. Ordem de implementacao recomendada

Nao construa tudo ao mesmo tempo. Cada marco abaixo termina com uma demo, testes,
um registro em `docs/lab/` e um commit. Estimativas sao deliberadamente abertas:
avance por evidencia, nao por calendario.

### M00 - Fundacao Python reproduzivel

**Aprenda:** venv, `pyproject.toml`, lockfile, layout `src`, imports, typing, Ruff,
mypy, pytest, Git, Compose, volumes e a fronteira HTTP. **Construa:** pacote
instalavel com `python -m live_caption_bridge`, um teste, logging no console,
dependencias fixadas e `infra/llm/compose.yaml` validado. **Perrengues:** interpreter
errado, ambiente nao ativado, engine Docker parado, porta ocupada e volume sem
espaco. **Pronto quando:** um clone limpo instala, testa e executa no Windows; o
servidor sobe pelo Compose, preserva modelos apos restart e responde a `/api/tags`.

Leitura: [tutorial Python](https://docs.python.org/3/tutorial/), [venv](https://docs.python.org/3/library/venv.html), [guia de `pyproject.toml`](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/), [pytest](https://docs.pytest.org/en/stable/getting-started.html) e [Git](https://git-scm.com/book/en/v2).

### M01 - Dominio e overlay falso

**Aprenda:** dataclasses, enums, Protocol, sinais/slots e regra do thread principal.
**Construa:** modelos da secao 5 e overlay que recebe legendas simuladas por uma
porta falsa. **Perrengues:** janela coletada, UI congelada e flags que mudam ao
alternar click-through. **Pronto quando:** teste unitario nao importa Qt e teste
`pytest-qt` atualiza o texto sem `sleep` arbitrario.

Leitura: [data classes](https://docs.python.org/3/library/dataclasses.html), [typing/Protocol](https://docs.python.org/3/library/typing.html#typing.Protocol), [Qt for Python](https://doc.qt.io/qtforpython-6/) e [pytest-qt](https://pytest-qt.readthedocs.io/en/latest/).

### M02 - Uma fonte de audio observavel

**Aprenda:** PCM, sample rate, mono/estereo, dBFS, context managers, thread e fila
limitada. **Construa:** enumerador e gravador de cinco segundos do microfone para
WAV, com medidor de nivel e timestamps. Ainda nao use STT. **Perrengues:** device
default muda, formato nao suportado, overflow e silencio. **Pronto quando:** o WAV
abre, duracao/formato batem e remover o dispositivo produz erro recuperavel.

Leitura: [modulo `wave`](https://docs.python.org/3/library/wave.html), [threading](https://docs.python.org/3/library/threading.html), [queue](https://docs.python.org/3/library/queue.html) e [SoundCard](https://soundcard.readthedocs.io/en/latest/).

### M03 - VAD, STT e legenda

**Aprenda:** segmentacao, VAD, inferencia, latencia e real-time factor. **Construa:**
microfone -> segmentos -> faster-whisper -> overlay, primeiro com WAV conhecido e
depois ao vivo. **Perrengues:** primeiro download, modelo lento, primeira silaba
cortada e fila crescente. **Pronto quando:** fala, silencio e ruido tem testes; RTF
fica sustentadamente abaixo de 1 ou o app degrada de modo visivel.

Leitura: [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [CTranslate2](https://opennmt.net/CTranslate2/) e [NumPy](https://numpy.org/doc/stable/user/absolute_beginners.html).

### M04 - Traducao por LLM e persistencia

**Aprenda:** HTTP, JSON Schema, timeout, retry, circuit breaker, SQL e transacoes.
**Construa:** provider falso primeiro; depois conecte o adaptador OpenAI-compatible
ao servidor Docker local, valide uma instancia centralizada, aplique schema estrito,
fallback para original e SQLite WAL. **Perrengues:** modelo ausente, JSON invalido,
429, servidor offline, resposta atrasada e texto sensivel em log. **Pronto quando:**
os testes simulam essas falhas sem travar captura, o endpoint pode mudar somente por
configuracao e nenhuma queda do container perde o original.

Leitura: [HTTPX](https://www.python-httpx.org/), [JSON Schema](https://json-schema.org/learn/getting-started-step-by-step), [SQLite](https://www.sqlite.org/lang.html) e a documentacao de timeouts/retries do provider escolhido. Registre no ADR qual provider e versao foram escolhidos; nao invente API a partir de memoria da LLM.

### M05 - Loopback e identidade das fontes

**Aprenda:** endpoint de renderizacao, WASAPI shared mode e loopback. **Construa:**
segundo worker para audio do sistema; mostre `MIC` e `SYSTEM` separadamente no
overlay e historico. **Perrengues:** DRM, Remote Desktop, troca de saida, Bluetooth
e microfone recapturando o alto-falante. **Pronto quando:** um WAV por fonte toca
isoladamente e as fontes simultaneas nunca trocam de identidade.

Leitura: [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording), [Core Audio APIs](https://learn.microsoft.com/en-us/windows/win32/coreaudio/core-audio-apis-in-windows-vista) e SoundCard da etapa M02.

### M06 - Replay de video sem audio

**Aprenda:** frame rate, codec versus container, keyframe, segmento, ring temporal
e processo filho. **Construa:** captura comprimida segmentada e hotkey que salva os
ultimos 30 segundos de video. **Perrengues:** RAM crescente, segmento em uso, FPS
irregular, caminho com espaco e processo FFmpeg morto. **Pronto quando:** `ffprobe`
confirma video/duracao e dois saves concorrentes nao apagam segmentos em uso.

Leitura: [FFmpeg](https://ffmpeg.org/ffmpeg.html), [formatos](https://ffmpeg.org/ffmpeg-formats.html), [mss](https://python-mss.readthedocs.io/) e [subprocess](https://docs.python.org/3/library/subprocess.html).

### M07 - Replay com trilhas separadas e sincronia

**Aprenda:** stream, canal, mux, PTS, drift, resampling e disposicao default.
**Construa:** rings independentes de microfone/sistema e MP4 com duas faixas
nomeadas; opcionalmente derive `Mixed`. **Perrengues:** uma stream comeca depois,
gap, drift, fonte mutada e player que toca apenas a default. **Pronto quando:**
`ffprobe` prova indices/titulos, cada faixa toca sozinha e o drift fica abaixo da
meta em 30 e 120 segundos.

Leitura: [selecao de streams e `-map`](https://ffmpeg.org/ffmpeg.html#Stream-selection), [stream specifiers](https://ffmpeg.org/ffmpeg.html#Stream-specifiers-1), [disposition](https://ffmpeg.org/ffmpeg.html#Advanced-options) e [ffprobe](https://ffmpeg.org/ffprobe.html).

### M08 - Produto resiliente

**Aprenda:** configuracao validada, hotkey Win32, observabilidade, privacidade e
degradacao. **Construa:** settings, recuperacao de devices, metricas, governor,
limpeza e indicadores de captura. **Perrengues:** hotkey ocupada, disco cheio,
permissao, sleep/resume e encerramento abrupto. **Pronto quando:** testes de falha
injetada deixam banco/arquivos validos e a UI continua responsiva.

Leitura: [RegisterHotKey](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey), [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/), [logging](https://docs.python.org/3/howto/logging.html) e [psutil](https://psutil.readthedocs.io/en/latest/).

### M09 - Qualidade, empacotamento e release

**Aprenda:** piramide de testes, profiling, soak, build reproduzivel, licencas e
instalador. **Construa:** suite final, benchmarks, teste contratual do servidor LLM,
PyInstaller e teste em Windows limpo. **Perrengues:** imagem/tag do servidor muda,
DLL/plugin Qt ausente, antivirus, modelo indisponivel e FFmpeg/licenca. **Pronto
quando:** outra pessoa sobe o servico documentado, instala o aplicativo e conclui o
roteiro E2E com URL local e centralizada; diagnostico e limitacoes estao no README.

Leitura: [PyInstaller](https://pyinstaller.org/en/stable/), [profiling Python](https://docs.python.org/3/library/profile.html), [licencas FFmpeg](https://ffmpeg.org/legal.html) e [Python Packaging User Guide](https://packaging.python.org/).

### M10 - Beta orientado por evidencia

**Aprenda:** triagem, reproducao, severidade, changelog e compatibilidade. **Faca:**
beta pequeno, telemetria somente opt-in e sem conteudo capturado, template de bug e
matriz de hardware. **Pronto quando:** cada incidente vira caso reproduzivel, teste
ou limitacao documentada; nenhuma falha e "resolvida" apenas por nao se repetir.

Em todos os marcos, nao avance porque os arquivos existem. Avance quando voce
consegue demonstrar, testar, explicar e diagnosticar o componente no hardware alvo.

## 21. Criterios para qualidade satisfatoria

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

## 22. Referencias tecnicas

- Qt for Python, flags de janela: <https://doc.qt.io/qtforpython-6/PySide6/QtCore/Qt.html>
- Qt for Python, widgets e translucidez: <https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QWidget.html>
- SoundCard e dispositivos de audio: <https://soundcard.readthedocs.io/en/latest/>
- faster-whisper: <https://github.com/SYSTRAN/faster-whisper>
- Ollama em Docker: <https://docs.ollama.com/docker>
- Compatibilidade OpenAI do Ollama: <https://docs.ollama.com/api/openai-compatibility>
- FFmpeg FAQ: <https://ffmpeg.org/faq.html>
- FFmpeg Filters/Formats/Devices: <https://ffmpeg.org/documentation.html>

Consulte sempre a documentacao da versao fixada no projeto. APIs, compatibilidade
de hardware e dependencias de runtime podem mudar.
