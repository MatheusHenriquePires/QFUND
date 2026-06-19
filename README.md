# QFund

QFund é uma aplicação em Python/FastAPI para consultar questões do banco Bernoulli, filtrar por disciplina, conteúdo, dificuldade e tipo, e gerar atividades em PDF com gabarito. O projeto também inclui telas HTML simples para uso local.

## Funcionalidades

- Listagem de disciplinas disponíveis no banco Bernoulli.
- Listagem de conteúdos por disciplina.
- Geração de atividades em PDF.
- Seleção aleatória de questões.
- Filtros por dificuldade e tipo de questão.
- Download de PDFs gerados anteriormente.
- Histórico de atividades por tipo de usuário ou professor.
- Persistência local do perfil do usuário.

## Tecnologias

- Python
- FastAPI
- Uvicorn
- Requests / HTTPX
- BeautifulSoup
- ReportLab
- python-dotenv

## Estrutura

```text
.
├── main.py                  # Inicialização da API FastAPI
├── routes.py                # Rotas HTTP da aplicação
├── schemas.py               # Modelos de entrada com Pydantic
├── requirements.txt         # Dependências Python
├── index.html               # Tela principal
├── history.html             # Tela de histórico
├── generated/               # Arquivos gerados e caches locais
│   ├── pdfs/                # PDFs das atividades
│   ├── images/              # Imagens baixadas para os PDFs
│   ├── history.json         # Histórico local
│   ├── user_profile.json    # Perfil local do usuário
│   ├── bernoulli_cache.json # Cache de disciplinas/conteúdos
│   └── bernoulli_responses.log # Log das respostas Bernoulli
├── models/                  # Modelos auxiliares
├── services/                # Regras de negócio e integrações
└── static/                  # Arquivos estáticos
```

## Pré-requisitos

- Python instalado.
- Credenciais válidas da API Bernoulli.
- Ambiente virtual Python recomendado.

## Configuração

Crie um arquivo `.env` na raiz do projeto com as credenciais:

```env
BERNOULLI_EMAIL=seu_email
BERNOULLI_PASSWORD=sua_senha
BERNOULLI_CACHE_TTL=3600
```

`BERNOULLI_CACHE_TTL` é opcional e define, em segundos, por quanto tempo o cache local de disciplinas será considerado válido.

## Instalação

No PowerShell, a partir da pasta do projeto:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Se o ambiente virtual já existir, basta ativá-lo e instalar as dependências:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Executando a API

Com o ambiente virtual ativado:

```powershell
uvicorn main:app --reload
```

A API ficará disponível em:

```text
http://127.0.0.1:8000
```

A tela principal também fica disponível nesse mesmo endereço:

```text
http://127.0.0.1:8000/
```

A documentação automática do FastAPI pode ser acessada em:

```text
http://127.0.0.1:8000/docs
```

## Usando as telas HTML

Com a API em execução, acesse as telas pelo navegador:

- `http://127.0.0.1:8000/`: tela principal para gerar atividades.
- `http://127.0.0.1:8000/history`: tela para consultar histórico e baixar PDFs gerados.

Os caminhos `/index.html` e `/history.html` também continuam disponíveis.

## Endpoints Principais

### `GET /disciplinas`

Retorna a lista de disciplinas disponíveis.

### `GET /conteudos/{disciplina_id}`

Retorna os conteúdos associados a uma disciplina.

### `POST /gerar-atividade`

Gera uma atividade em PDF e retorna o arquivo para download.

Exemplo de corpo:

```json
{
  "disciplina_id": "1",
  "conteudos": [10, 20],
  "quantidade": 10,
  "dificuldade": "facil",
  "tipo": "objetiva",
  "incluir_gabarito": false,
  "titulo": "Atividade de Revisao",
  "tipo_usuario": "professor",
  "professor": "Nome do Professor"
}
```

### `GET /historico/tipo/{tipo}`

Lista atividades geradas por tipo de usuário.

### `GET /historico/professor/{nome}`

Lista atividades geradas por professor responsável.

### `GET /historico/download/{filename}`

Baixa um PDF gerado anteriormente.

### `GET /usuario`

Retorna o perfil salvo localmente.

### `POST /usuario`

Salva o perfil local do usuário.

Exemplo:

```json
{
  "nome": "Maria",
  "tipo": "professor",
  "disciplina_preferida": "Matematica"
}
```

## Arquivos Gerados

Os arquivos de saída ficam em `generated/`:

- PDFs: `generated/pdfs/`
- Imagens extraídas das questões: `generated/images/`
- Histórico: `generated/history.json`
- Perfil local: `generated/user_profile.json`
- Cache Bernoulli: `generated/bernoulli_cache.json`
- Log das respostas Bernoulli: `generated/bernoulli_responses.log`

## Log Bernoulli

Sempre que a aplicação carregar disciplinas, conteúdos ou questões da integração Bernoulli, uma entrada será adicionada em:

```text
generated/bernoulli_responses.log
```

O arquivo usa o formato JSONL: cada linha é um JSON independente com `ts`, `evento`, `metadata` e `payload`.

## Observações

- O projeto depende da API Bernoulli para consultar disciplinas, conteúdos e questões.
- As credenciais não devem ser versionadas no repositório.
- O PDF é gerado com gabarito ao final.
- O campo `incluir_gabarito` existe no schema, mas a geração atual sempre adiciona a página de gabarito.
- O filtro de conteúdo é recebido pela rota, mas a implementação atual da geração usa esse valor apenas para exibição no PDF.
