# StockCentral

API de gerenciamento de estoque desenvolvida para o desafio Back-End da Ecomp Jr.

## Etapa atual

A API possui verificações de funcionamento, conexão com PostgreSQL e CRUD de
categorias, fornecedores e produtos. Produtos possuem filtros por categoria,
fornecedor e estoque mínimo. Há migrações e testes automatizados com PostgreSQL real.
Movimentações e consultas do histórico serão implementadas nas próximas etapas.
Autenticação ainda não está implementada.

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
- A exclusão de categorias com produtos vinculados é bloqueada pelo banco e
  retorna 409. Excluir uma categoria não apaga seus produtos.

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

## Rotas de fornecedores

| Método | Caminho | Sucesso |
| --- | --- | --- |
| POST | `/fornecedores` | 201, fornecedor criado |
| GET | `/fornecedores?offset=0&limit=50` | 200, lista ordenada por ID |
| GET | `/fornecedores/{supplier_id}` | 200, fornecedor encontrado |
| PUT | `/fornecedores/{supplier_id}` | 200, fornecedor atualizado |
| DELETE | `/fornecedores/{supplier_id}` | 204, corpo vazio |

POST e PUT recebem os quatro campos abaixo. PUT substitui os dados do fornecedor;
todos os campos são obrigatórios. Exemplo com dados para demonstração:

```json
{
  "nome": "Fornecedor de exemplo",
  "cnpj": "12.ABC.345/01DE-35",
  "email": "contato@example.com",
  "telefone": "(75) 99999-1234"
}
```

A resposta inclui `id`, gerado pelo banco, e os quatro campos. A listagem retorna
um array ou `[]`. Os limites de paginação são os mesmos das categorias.

- **Nome:** 1 a 150 caracteres, com espaços nas pontas removidos. Nomes de
  fornecedores podem se repetir; CNPJ e email identificam as duplicatas.
- **CNPJ:** aceita formato numérico ou alfanumérico, sem pontuação ou com a máscara
  completa `XX.XXX.XXX/XXXX-XX`. Valida os dois dígitos verificadores e salva os
  14 caracteres sem pontuação, com letras maiúsculas. Isso não consulta a situação
  cadastral da empresa. O algoritmo e o exemplo alfanumérico seguem o
  [manual de DV da Receita Federal](https://www.gov.br/receitafederal/pt-br/centrais-de-conteudo/publicacoes/documentos-tecnicos/cnpj/manual-dv-cnpj.pdf).
- **Email:** usa `EmailStr` do Pydantic e a dependência `email-validator` para
  validar o formato. O sistema salva em minúsculas e considera endereços iguais
  mesmo que tenham diferenças de maiúsculas/minúsculas. Não verifica a existência
  da caixa de email. Limite de 254 caracteres após a validação.
- **Telefone:** texto de até 30 caracteres, contendo de 8 a 15 dígitos. Aceita
  espaços, parênteses, ponto, hífen e `+` no início. Preserva a formatação e remove
  espaços nas pontas. Não consulta operadoras nem valida se o número existe.
- **Unicidade:** o PostgreSQL impede CNPJ duplicado e email duplicado sem
  diferenciar maiúsculas/minúsculas, inclusive em gravações simultâneas. A API
  normaliza o CNPJ antes da gravação; o banco exige seu formato sem máscara.
- Campos desconhecidos, campos ausentes ou valores inválidos retornam **422**.
  IDs inexistentes retornam **404**. CNPJ ou email já utilizado retorna **409**, com
  uma mensagem indicando o campo. Uma edição rejeitada mantém os dados anteriores.
- A exclusão de fornecedores com produtos vinculados retorna **409**. O banco
  protege esse vínculo; excluir o fornecedor não apaga seus produtos.

### Aplicando esta etapa em uma instalação existente

No **PowerShell do VS Code**, na **raiz do projeto**, com o banco em execução:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
```

O primeiro comando instala também a dependência de validação de email. O segundo
aplica as migrações pendentes: `0002` cria fornecedores e `0003` cria produtos,
preservando os cadastros existentes.
Não precisa entrar na pasta `.venv`: o caminho chama diretamente o Python dela.
Inicie a API conforme as instruções anteriores e procure **Fornecedores** e
**Produtos** em `/docs`.

## Rotas de produtos

Cada produto pertence a uma categoria e a um fornecedor. Os campos `categoria_id`
e `fornecedor_id` são chaves estrangeiras: apontam para IDs de registros existentes.
Uma categoria ou um fornecedor pode ter vários produtos.

| Método | Caminho | Entrada | Sucesso |
| --- | --- | --- | --- |
| POST | `/produtos` | JSON de cadastro | 201, produto com saldo zero |
| GET | `/produtos` | Filtros e paginação opcionais | 200, array de produtos ou `[]` |
| GET | `/produtos/{product_id}` | ID inteiro positivo | 200, produto |
| PUT | `/produtos/{product_id}` | ID e JSON completo de cadastro | 200, produto atualizado |
| DELETE | `/produtos/{product_id}` | ID inteiro positivo | 204, corpo vazio |

### Cadastro e edição

Primeiro cadastre uma categoria e um fornecedor. Use os IDs retornados no exemplo
abaixo, substituindo `1` pelos IDs reais. Todos os sete campos são obrigatórios
tanto no POST quanto no PUT:

```json
{
  "nome": "Caneta azul",
  "sku": "CANETA-001",
  "preco_custo": "2.50",
  "preco_venda": "4.90",
  "estoque_minimo": 5,
  "categoria_id": 1,
  "fornecedor_id": 1
}
```

Exemplo de resposta (os IDs e a data são ilustrativos):

```json
{
  "id": 1,
  "nome": "Caneta azul",
  "sku": "CANETA-001",
  "preco_custo": "2.50",
  "preco_venda": "4.90",
  "quantidade_em_estoque": 0,
  "estoque_minimo": 5,
  "data_cadastro": "2026-10-18T12:00:00Z",
  "categoria_id": 1,
  "fornecedor_id": 1
}
```

- **Nome:** de 1 a 150 caracteres após remover espaços nas pontas.
- **SKU:** código único, de 1 a 64 caracteres, iniciado por letra ou número.
  Aceita letras ASCII, números, ponto, hífen e sublinhado. A API remove espaços nas
  pontas e converte para maiúsculas; `caneta-001` e `CANETA-001` são o mesmo código.
  O banco exige esse formato e garante a unicidade.
- **Preços:** de zero a `9999999999.99`, com até duas casas decimais. Usamos
  `Decimal` no Python e `Numeric(12, 2)` no PostgreSQL para preservar os centavos.
  A resposta JSON representa preços como strings. Na entrada, envie strings com
  ponto decimal, como nos exemplos; números JSON também são aceitos. Não existe
  restrição de venda acima do custo, permitindo descontos e liquidações.
- **Estoque mínimo:** inteiro entre 0 e 2147483647, indicando o limite de reposição.
- **Categoria e fornecedor:** IDs inteiros positivos de cadastros existentes.
  É possível trocar esses vínculos pelo PUT. A FK com `RESTRICT` impede excluir
  categorias e fornecedores enquanto forem usados por algum produto.
- **Saldo e data:** gerados pelo servidor, somente leitura. O saldo inicial é
  zero; a data possui fuso horário. POST e PUT rejeitam `quantidade_em_estoque`,
  `data_cadastro`, `id` ou qualquer campo extra. PUT não altera saldo nem data.
  As movimentações que atualizarão o saldo serão implementadas na próxima etapa.

### Filtros

| Parâmetro | Regra |
| --- | --- |
| `offset` | Inteiro >= 0; padrão 0 |
| `limit` | Inteiro de 1 a 100; padrão 50 |
| `categoria_id` | Somente produtos da categoria informada |
| `fornecedor_id` | Somente produtos do fornecedor informado |
| `estoque_baixo` | `true`: saldo <= mínimo; `false`: saldo > mínimo; omitido: todos |

Os filtros podem ser combinados. A filtragem ocorre antes da paginação; a ordem
é sempre pelo ID. Um filtro sem resultados retorna `[]`, incluindo IDs de
categoria/fornecedor que não existem. Exemplos:

```text
GET /produtos?estoque_baixo=true
GET /produtos?categoria_id=1&fornecedor_id=1&limit=10
GET /produtos?estoque_baixo=true&offset=10&limit=10
```

### Erros de produtos

| Status | Situação | Corpo |
| --- | --- | --- |
| 404 | Produto inexistente em GET individual, PUT ou DELETE | `{"detail":"Produto nao encontrado."}` |
| 409 | SKU já utilizado | `{"detail":"Ja existe um produto com esse SKU."}` |
| 409 | Exclusão impedida por vínculo protegido | `{"detail":"Produto vinculado a outros registros nao pode ser excluido."}` |
| 422 | Categoria inexistente no POST ou PUT | `{"detail":"Categoria informada nao existe."}` |
| 422 | Fornecedor inexistente no POST ou PUT | `{"detail":"Fornecedor informado nao existe."}` |
| 422 | Campos, ID ou filtros inválidos | `detail` contém a lista de erros do FastAPI, como no exemplo de categorias |
| 503 | Falha operacional de banco | `{"detail":"Banco de dados indisponivel."}` |
| 500 | Outro erro de banco | `{"detail":"Erro interno ao acessar o banco de dados."}` |

Gravações rejeitadas desfazem sua transação, preservando todos os dados anteriores.
Nesta etapa ainda não há movimentações vinculadas a produtos; a proteção desse
histórico será adicionada junto à tabela de movimentações.

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
Também confere as restrições de unicidade diretamente no PostgreSQL, os dígitos
verificadores de CNPJs numéricos/alfanuméricos e a preservação de categorias ao
reverter e reaplicar apenas a migração de fornecedores.
Para produtos, cobre preços e seus limites, SKU, integridade dos relacionamentos,
bloqueio de exclusão de categorias/fornecedores, preservação de saldo e data,
combinação de filtros e migração sem perder os cadastros anteriores. Os cenários
de filtro preparam saldos diretamente no schema temporário de teste.

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
| `app/routers/suppliers.py` | Endpoints de fornecedores e tratamento de duplicatas |
| `app/routers/products.py` | CRUD de produtos, filtros e tratamento de vínculos inválidos |
| `app/validators.py` | Cálculo dos dígitos do CNPJ e validação de telefone |
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

1. Movimentações imutáveis com atualização transacional do saldo.
2. Consultas de movimentações por período e fornecedor.
3. Padronização de erros, logs estruturados e ampliação dos testes.
