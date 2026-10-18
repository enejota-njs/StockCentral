# StockCentral

API de gerenciamento de estoque desenvolvida para o desafio Back-End da Ecomp Jr.

## Etapa atual

A API possui verificações de funcionamento, conexão com PostgreSQL e CRUD de
categorias. Há migração da tabela e testes automatizados com PostgreSQL real.
Fornecedores, produtos, movimentações e consultas de estoque serão implementados
nas próximas etapas. Autenticação ainda não está implementada.

## Tecnologias

- Python 3.13, FastAPI e Uvicorn.
- PostgreSQL 18 executado pelo Docker Compose.
- SQLAlchemy e Psycopg para o acesso ao banco.
- Pydantic Settings para configurações e Pydantic para validar os dados.
- Alembic para migrações; Pytest e HTTPX para testes.

## Preparação no Windows com Docker no WSL

Todos os comandos devem ser executados na raiz do repositório. O ambiente Python
usado abaixo é o do Windows; execute Docker no terminal WSL. Não é necessário
entrar na pasta `.venv` ou ativá-la: os comandos chamam seu Python diretamente.

### PowerShell: preparar o Python

Na primeira instalação:

```powershell
cd C:\Users\enejo\dev\StockCentral
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Se a `.venv` já existir, execute apenas a instalação das dependências.

Na primeira configuração, copie `.env.example` para `.env` e preencha a senha:

```powershell
Copy-Item .env.example .env
```

Não repita essa cópia se já tiver um `.env` configurado. Mantenha a senha local,
fora do Git. As variáveis esperadas são:

| Variável | Configuração local |
| --- | --- |
| `POSTGRES_DB` | `stockcentral` |
| `POSTGRES_USER` | `postgres` (administrador do banco local) |
| `POSTGRES_PASSWORD` | Senha escolhida por você |
| `POSTGRES_HOST` | `127.0.0.1` |
| `POSTGRES_PORT` | `5444` |

### WSL: iniciar o banco

```bash
cd /mnt/c/Users/enejo/dev/StockCentral
docker compose up -d
docker compose ps
```

O Compose publica o PostgreSQL em `127.0.0.1:5444` e mantém os dados no volume
`postgres_data`. A porta interna do contêiner é `5432`. Alterar a senha no `.env`
depois da primeira inicialização não altera a senha já gravada no banco.

Mantenha o terminal Ubuntu/WSL aberto enquanto usa a API. Para manter o Compose
em primeiro plano e acompanhar o banco, pode usar `docker compose up` sem `-d`;
nesse caso, esse terminal fica ocupado e `Ctrl+C` para o serviço.

### PowerShell: aplicar migrações e iniciar a API

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

O primeiro comando cria/atualiza as tabelas conforme as migrações pendentes.
Ele pode ser repetido: revisões já aplicadas não são executadas novamente.
O segundo inicia o servidor; `--reload` é indicado para desenvolvimento.

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI: <http://127.0.0.1:8000/openapi.json>
- Funcionamento da API: <http://127.0.0.1:8000/health>
- Conexão com o banco: <http://127.0.0.1:8000/health/db>

Use `Ctrl+C` para parar a API. Para parar o banco, execute `docker compose stop`
no WSL. Não use `docker compose down -v` para parar: `-v` remove os dados do volume.

## Rotas de categorias

| Método | Caminho | Entrada | Sucesso |
| --- | --- | --- | --- |
| POST | `/categorias` | JSON com `nome` | 201, categoria criada |
| GET | `/categorias` | Query `offset=0` e `limit=50` | 200, lista de categorias |
| GET | `/categorias/{category_id}` | ID inteiro positivo no caminho | 200, categoria |
| PUT | `/categorias/{category_id}` | ID e JSON com `nome` | 200, categoria atualizada |
| DELETE | `/categorias/{category_id}` | ID inteiro positivo no caminho | 204, corpo vazio |

Exemplo de corpo para POST e PUT:

```json
{"nome": "Eletrônicos"}
```

Exemplo de resposta para POST, GET individual e PUT (o ID é gerado pelo banco):

```json
{"id": 1, "nome": "Eletrônicos"}
```

A listagem retorna um array desses objetos, ou `[]` quando não há resultados.
`offset` deve ser zero ou positivo; `limit` deve estar entre 1 e 100.
Exemplo: `/categorias?offset=10&limit=5` pula dez registros e retorna até cinco,
ordenados por ID.

### Regras e erros

- O nome é obrigatório, tem de 1 a 100 caracteres após remover espaços nas pontas.
- Campos adicionais no corpo são rejeitados.
- A comparação de duplicatas ignora maiúsculas/minúsculas, preservando a grafia
  cadastrada. `Papelaria` e `PAPELARIA` não podem coexistir.
- A unicidade é garantida por um índice do PostgreSQL, inclusive para gravações
  que não passam pela API.
- Uma escrita rejeitada desfaz sua transação. Uma tentativa inválida de edição
  preserva os dados anteriores.
- Produtos ainda não existem nesta etapa; a relação que bloqueará a exclusão de
  categorias com produtos será criada na migração de produtos.

| Status | Quando ocorre | Resposta |
| --- | --- | --- |
| 404 | ID não encontrado em GET individual, PUT ou DELETE | `{"detail":"Categoria nao encontrada."}` |
| 409 | Nome duplicado em POST ou PUT | `{"detail":"Ja existe uma categoria com esse nome."}` |
| 409 | Banco impede DELETE por vínculo com outro registro | `{"detail":"Categoria vinculada a outros registros nao pode ser excluida."}` |
| 422 | Corpo, ID ou parâmetros inválidos | `detail` contém uma lista de erros de validação |
| 503 | Falha operacional de conexão com o banco | `{"detail":"Banco de dados indisponivel."}` |
| 500 | Outro erro SQLAlchemy não tratado especificamente | `{"detail":"Erro interno ao acessar o banco de dados."}` |

Exemplo de validação de nome vazio:

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "nome"],
      "msg": "String should have at least 1 character",
      "input": "",
      "ctx": {"min_length": 1}
    }
  ]
}
```

O Swagger documenta os corpos, parâmetros e respostas de cada rota. Os detalhes
de exceções de banco não são enviados ao cliente. A padronização completa de
erros e os logs estruturados serão aprimorados nas próximas etapas.

## Testes automatizados

Com PostgreSQL em execução e `.env` configurado, no PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes usam PostgreSQL real. Cada teste cria um schema de nome aleatório,
aplica as migrações e desfaz a transação externa ao terminar. As sessões da API
usam savepoints, de modo que seus commits não persistem os dados do teste.
O usuário de teste precisa poder criar schemas; a conta local `postgres` permite
isso. Não execute esses testes contra um banco de produção.

A suíte cobre CRUD, duplicatas, limites de nomes, entradas inválidas, paginação,
preservação de dados em falhas, respostas de erro e reversão de migrações.
Também confere a restrição de unicidade diretamente no PostgreSQL.

Para conferir se os modelos correspondem às migrações aplicadas:

```powershell
.\.venv\Scripts\python.exe -m alembic check
```

O workflow `.github/workflows/tests.yml` executa os testes a cada push e pull
request. Ele inicia um PostgreSQL descartável no GitHub, instala dependências,
aplica migrações e confere a consistência dos modelos. A senha presente no
workflow é exclusiva desse serviço temporário e não utiliza seu `.env` local.
O resultado fica na aba **Actions** do repositório após o push.

## Organização dos arquivos

| Caminho | Responsabilidade |
| --- | --- |
| `app/main.py` | Aplicação FastAPI, health checks e registro de rotas/erros |
| `app/config.py` | Leitura e validação de configurações |
| `app/database.py` | Engine, base dos modelos e sessões |
| `app/models.py` | Tabelas e restrições SQLAlchemy |
| `app/schemas.py` | Corpos de entrada e saída Pydantic |
| `app/routers/categories.py` | Endpoints de categorias e transações |
| `app/errors.py` | Respostas para erros de banco |
| `migrations/` | Histórico da estrutura do banco |
| `tests/` | Fixtures isoladas e cenários de integração |
| `compose.yaml` | Serviço PostgreSQL local e volume persistente |

## Se a conexão falhar

1. No WSL, confira `docker compose ps` e `docker compose logs --tail 30 db`.
2. Confira se o Ubuntu/WSL e o Docker estão em execução.
3. No PowerShell, use `Test-NetConnection 127.0.0.1 -Port 5444` para conferir a porta.
4. Confira localmente usuário, banco e senha no `.env`, sem enviá-los ao GitHub.
5. Se `/health/db` funcionar, mas categorias falhar, confirme que executou
   `python -m alembic upgrade head` usando o Python da `.venv`.

## Próximas etapas

1. Fornecedores, incluindo CNPJ e email únicos.
2. Produtos, relacionamentos, preços e estoque mínimo.
3. Movimentações imutáveis com atualização transacional do saldo.
4. Consultas por estoque mínimo, período e fornecedor.
5. Padronização de erros, logs estruturados e ampliação dos testes.
