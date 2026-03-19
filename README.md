# Auto+ Backend — API Flask + PostgreSQL

## Stack
- Python 3.12 + Flask 3
- PostgreSQL 16 (local Docker, produção Supabase ou Fly Postgres)
- JWT para auth, bcrypt para senha
- psycopg2 com connection pool

---

## Rodar local (Docker)

```bash
cp .env.example .env        # ajuste se quiser
docker compose up --build   # sobe API + Postgres
```

API em http://localhost:5000  
Postgres em localhost:5432  
O schema é aplicado automaticamente na primeira subida.

---

## Rodar sem Docker

```bash
pip install -r requirements.txt
cp .env.example .env
# edite DATABASE_URL no .env
python run.py
```

---

## Endpoints principais

### Auth
POST  /api/auth/login          — retorna JWT
GET   /api/auth/me             — usuário logado
POST  /api/auth/trocar-senha

### Clientes
GET    /api/clientes/           ?q=busca&pagina=1
GET    /api/clientes/:id
GET    /api/clientes/cpf/:cpf   — busca por CPF (usado no wizard de venda)
POST   /api/clientes/
PUT    /api/clientes/:id
DELETE /api/clientes/:id        — soft delete

### Veículos
GET    /api/veiculos/           ?status=disponivel&tipo=Hatch&q=
GET    /api/veiculos/:id
POST   /api/veiculos/
PUT    /api/veiculos/:id
DELETE /api/veiculos/:id

### Vendas
GET    /api/vendas/
GET    /api/vendas/:id          — inclui parcelas geradas
POST   /api/vendas/             — gera parcelas automaticamente
DELETE /api/vendas/:id          — cancela + devolve veículo ao estoque

### Financeiro
GET    /api/financeiro/parcelas         ?status=vencido  ou ?alertas=1
POST   /api/financeiro/parcelas/:id/receber
GET    /api/financeiro/contas
POST   /api/financeiro/contas
POST   /api/financeiro/contas/:id/pagar
DELETE /api/financeiro/contas/:id
GET    /api/financeiro/resumo           — KPIs financeiros

### Dashboard
GET    /api/dashboard/          — KPIs + atividade + alertas

### Configurações
GET    /api/config/
PUT    /api/config/
PUT    /api/config/api-toggle   — {"api":"fipe","ativo":true}

### APIs Externas (proxy autenticado)
GET  /api/ext/cep/:cep
GET  /api/ext/fipe/marcas/:tipo
GET  /api/ext/fipe/marcas/:tipo/:marca/modelos
GET  /api/ext/fipe/marcas/:tipo/:marca/modelos/:modelo/anos
GET  /api/ext/fipe/marcas/:tipo/:marca/modelos/:modelo/anos/:ano/preco
GET  /api/ext/placa/:placa

---

## Autenticação

Todos os endpoints (exceto /api/auth/login e /health) exigem:
  Authorization: Bearer <token>

---

## Deploy no Fly.io

```bash
fly auth login
fly launch --name automais-api --region gru
fly secrets set JWT_SECRET=sua-chave-longa
fly secrets set DATABASE_URL=postgresql://...
fly deploy
```

---

## Seed

Usuário padrão criado pelo schema:
  Email: admin@jpautomóveis.com.br
  Senha: admin123

Troque em produção.
