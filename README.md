# 📚 QFund

<p align="center">
  <img src="docs/banner.png" alt="QFund Banner" width="100%">
</p>

<p align="center">
  <strong>Gerador inteligente de atividades escolares integrado ao banco Bernoulli.</strong>
</p>

<p align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![ReportLab](https://img.shields.io/badge/PDF-ReportLab-red?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-orange?style=for-the-badge)

</p>

---

# 📖 Sobre

O **QFund** é uma plataforma desenvolvida em **Python + FastAPI** para geração automática de atividades escolares utilizando o banco de questões do **Bernoulli Sistema de Ensino**.

A aplicação permite selecionar disciplinas, conteúdos, dificuldades, tipos de questões e gerar **PDFs profissionais**, prontos para impressão, contendo:

- Cabeçalho personalizado;
- Questões objetivas e discursivas;
- Imagens das questões;
- Espaço inteligente para respostas;
- Gabarito automático;
- Histórico de atividades;
- Cache das consultas.

---

# ✨ Funcionalidades

- ✅ Integração com a API Bernoulli
- ✅ Consulta de disciplinas
- ✅ Consulta de conteúdos
- ✅ Seleção aleatória de questões
- ✅ Filtros por dificuldade
- ✅ Filtros por tipo de questão
- ✅ Geração automática de PDFs
- ✅ Cabeçalho profissional
- ✅ Logo personalizado
- ✅ Questões com imagens
- ✅ Área de resposta inteligente
- ✅ Gabarito automático
- ✅ Histórico das atividades
- ✅ Download de PDFs
- ✅ Perfil do usuário
- ✅ Cache das consultas
- ✅ Interface Web

---

# 🖼 Interface

## Tela Principal

![Tela Principal](docs/home.png)

---

## Histórico

![Histórico](docs/history.png)

---

## PDF Gerado

![PDF](docs/pdf.png)

---

# 📄 Características do PDF

Os PDFs gerados possuem:

- Logo institucional
- Cabeçalho profissional
- Nome do aluno
- Professor
- Disciplina
- Data
- Série
- Turno
- Questões numeradas
- Alternativas formatadas
- Imagens centralizadas
- Área inteligente para resposta
- Gabarito em página separada
- Numeração automática das páginas

---

# 🚀 Tecnologias

- Python
- FastAPI
- Uvicorn
- Requests
- HTTPX
- BeautifulSoup4
- ReportLab
- python-dotenv
- Pydantic

---

# 🏗 Arquitetura

```text
                        Usuário
                           │
                           ▼
                 Interface HTML / JS
                           │
                           ▼
                      FastAPI
                           │
                           ▼
                  Camada de Serviços
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                     ▼
 API Bernoulli                     Gerador de PDF
        │                                     │
        ▼                                     ▼
   Cache Local                     ReportLab PDF
        │                                     │
        └──────────────────┬──────────────────┘
                           ▼
                   Arquivos Gerados
```

---

# 📁 Estrutura do Projeto

```text
QFund/
│
├── assets/
│   └── logo_proposito.png
│
├── docs/
│   ├── banner.png
│   ├── home.png
│   ├── history.png
│   └── pdf.png
│
├── generated/
│   ├── images/
│   ├── pdfs/
│   ├── bernoulli_cache.json
│   ├── bernoulli_responses.log
│   ├── history.json
│   └── user_profile.json
│
├── models/
│
├── services/
│   ├── atividade_service.py
│   ├── bernoulli.py
│   ├── history_service.py
│   ├── pdf_generator.py
│   └── profile_service.py
│
├── static/
│
├── index.html
├── history.html
├── main.py
├── routes.py
├── schemas.py
├── requirements.txt
├── .env
└── README.md
```

---

# ⚙ Pré-requisitos

- Python 3.11+
- Conta Bernoulli
- Credenciais válidas da API
- Ambiente virtual Python

---

# 🔧 Configuração

Crie um arquivo `.env`

```env
BERNOULLI_EMAIL=seu_email
BERNOULLI_PASSWORD=sua_senha
BERNOULLI_CACHE_TTL=3600
```

O parâmetro `BERNOULLI_CACHE_TTL` é opcional.

---

# 📦 Instalação

Clone o projeto

```bash
git clone https://github.com/seuusuario/QFund.git
```

Entre na pasta

```bash
cd QFund
```

Crie o ambiente virtual

Windows

```powershell
python -m venv venv
```

Linux

```bash
python3 -m venv venv
```

Ative

Windows

```powershell
.\venv\Scripts\Activate.ps1
```

Linux

```bash
source venv/bin/activate
```

Instale as dependências

```bash
pip install -r requirements.txt
```

---

# ▶ Executando

```bash
uvicorn main:app --reload
```

A aplicação ficará disponível em

```
http://127.0.0.1:8000
```

Swagger

```
http://127.0.0.1:8000/docs
```

---

# 🌐 Interface

Página principal

```
http://127.0.0.1:8000/
```

Histórico

```
http://127.0.0.1:8000/history
```

---

# 📌 Endpoints

## GET /disciplinas

Lista disciplinas.

---

## GET /conteudos/{disciplina_id}

Lista conteúdos.

---

## POST /gerar-atividade

Gera um PDF.

### Exemplo

```json
{
  "disciplina_id": "1",
  "conteudos": [
    10,
    20
  ],
  "quantidade": 10,
  "dificuldade": "facil",
  "tipo": "objetiva",
  "titulo": "Atividade de Revisão",
  "professor": "Carlos Eduardo",
  "tipo_usuario": "professor",
  "incluir_gabarito": true
}
```

---

## GET /historico/tipo/{tipo}

Consulta histórico.

---

## GET /historico/professor/{nome}

Consulta por professor.

---

## GET /historico/download/{arquivo}

Download do PDF.

---

## GET /usuario

Obtém o perfil salvo.

---

## POST /usuario

Salva o perfil.

```json
{
    "nome":"Maria",
    "tipo":"professor",
    "disciplina_preferida":"Matemática"
}
```

---

# 📂 Arquivos Gerados

```
generated/

├── pdfs/
├── images/
├── history.json
├── user_profile.json
├── bernoulli_cache.json
└── bernoulli_responses.log
```

---

# 📜 Log Bernoulli

Toda comunicação com a API Bernoulli é registrada automaticamente.

Formato:

```json
{
    "ts":"",
    "evento":"",
    "metadata":{},
    "payload":{}
}
```

---

# ⚡ Recursos Inteligentes

O gerador identifica automaticamente o tipo da questão.

### Questões Discursivas

Adiciona linhas para resposta.

### Questões de Matemática

Adiciona espaço para cálculos.

### Questões Curtas

Adiciona poucas linhas.

### Questões Longas

Adiciona várias linhas automaticamente.

---

# 🗂 Roadmap

- [x] Integração Bernoulli
- [x] Cache
- [x] Histórico
- [x] Perfil do usuário
- [x] PDF profissional
- [x] Geração automática
- [x] Questões com imagens
- [x] Gabarito
- [ ] Login
- [ ] Banco de dados
- [ ] Docker
- [ ] Testes automatizados
- [ ] Painel administrativo
- [ ] Exportação DOCX
- [ ] Geração de provas em lote

---

# 🤝 Contribuindo

1. Faça um Fork

2. Crie uma branch

```bash
git checkout -b feature/minha-feature
```

3. Commit

```bash
git commit -m "Minha nova feature"
```

4. Push

```bash
git push origin feature/minha-feature
```

5. Abra um Pull Request.

---

# 📄 Licença

Este projeto está licenciado sob a licença **MIT**.

---

# 👨‍💻 Autor

**Matheus Henrique**

Estudante de Análise e Desenvolvimento de Sistemas.

Desenvolvedor Full Stack apaixonado por automação, inteligência artificial e desenvolvimento de soluções para educação.

---

<p align="center">
Desenvolvido com ❤️ utilizando Python, FastAPI e ReportLab.
</p>