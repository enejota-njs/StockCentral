# StockCentral

API de gerenciamento de estoque desenvolvida para o desafio Back-End da Ecomp Jr.

## Tecnologias

- Python 3.13 e FastAPI
- PostgreSQL 18 e Docker Compose
- SQLAlchemy e Alembic
- Pydantic e Pytest

## Executando localmente

Execute os comandos na raiz do projeto. No Windows, use o PowerShell para Python
e o terminal WSL para Docker. Os comandos abaixo usam diretamente o Python da
`.venv`, sem precisar ativar o ambiente ou entrar nessa pasta.

### Configuração — PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Crie o ambiente e copie o `.env` somente na primeira configuração. Preencha
`POSTGRES_PASSWORD` no `.env` e mantenha esse arquivo fora do Git.
A conexão local usa `127.0.0.1` e a porta `5444`.

### Banco de dados — WSL

```bash
docker compose up -d
```

Mantenha o WSL em execução enquanto utiliza a aplicação.

### Aplicação — PowerShell

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

A documentação interativa fica disponível em
[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Testes

Com o banco em execução e o `.env` configurado, execute no PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes utilizam PostgreSQL e schemas temporários isolados.
