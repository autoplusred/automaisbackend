-- ============================================================
--  AUTO+ — Schema PostgreSQL (Supabase-compatible)
--  Multi-tenant: toda tabela tem empresa_id
--  Execute como superuser ou owner do schema
-- ============================================================

-- Extensões
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- ============================================================
--  EMPRESAS (tenants)
-- ============================================================
CREATE TABLE empresas (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome          TEXT NOT NULL,
    cnpj          TEXT UNIQUE,
    telefone      TEXT,
    email         TEXT,
    cep           TEXT,
    logradouro    TEXT,
    numero        TEXT,
    bairro        TEXT,
    cidade        TEXT,
    estado        CHAR(2),
    plano         TEXT NOT NULL DEFAULT 'basico', -- basico | pro | enterprise
    ativo         BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
--  USUÁRIOS
-- ============================================================
CREATE TABLE usuarios (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id    UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nome          TEXT NOT NULL,
    email         TEXT NOT NULL,
    senha_hash    TEXT NOT NULL,
    perfil        TEXT NOT NULL DEFAULT 'vendedor', -- proprietario | gerente | vendedor | caixa
    ativo         BOOLEAN NOT NULL DEFAULT TRUE,
    ultimo_login  TIMESTAMPTZ,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(empresa_id, email)
);

-- ============================================================
--  CLIENTES
-- ============================================================
CREATE TABLE clientes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    -- pessoal
    nome            TEXT NOT NULL,
    cpf             TEXT,
    rg              TEXT,
    cnh             TEXT,
    data_nascimento DATE,
    estado_civil    TEXT,
    profissao       TEXT,
    renda_mensal    NUMERIC(12,2),
    -- contato
    telefone        TEXT,
    telefone_fixo   TEXT,
    email           TEXT,
    -- endereço
    cep             TEXT,
    logradouro      TEXT,
    numero          TEXT,
    complemento     TEXT,
    bairro          TEXT,
    cidade          TEXT,
    estado          CHAR(2),
    -- meta
    observacoes     TEXT,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(empresa_id, cpf)
);

CREATE INDEX idx_clientes_empresa ON clientes(empresa_id);
CREATE INDEX idx_clientes_cpf     ON clientes(empresa_id, cpf);
CREATE INDEX idx_clientes_nome    ON clientes USING gin(to_tsvector('portuguese', nome));

-- ============================================================
--  VEÍCULOS
-- ============================================================
CREATE TABLE veiculos (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    -- identificação
    placa           TEXT,
    renavam         TEXT,
    chassi          TEXT,
    -- fipe
    fipe_codigo     TEXT,
    fipe_marca      TEXT,
    fipe_marca_cod  TEXT,
    fipe_modelo     TEXT,
    fipe_modelo_cod TEXT,
    fipe_ano_cod    TEXT,
    fipe_preco      NUMERIC(12,2),
    fipe_referencia TEXT,     -- ex: "março/2026"
    -- dados
    marca           TEXT NOT NULL,
    modelo          TEXT NOT NULL,
    versao          TEXT,
    tipo            TEXT,     -- Hatch | Sedan | SUV | Pickup | Moto | Outro
    ano_fabricacao  SMALLINT,
    ano_modelo      SMALLINT,
    km              INTEGER,
    cor             TEXT,
    combustivel     TEXT,
    cambio          TEXT,
    -- financeiro
    preco_custo     NUMERIC(12,2),
    preco_venda     NUMERIC(12,2),
    -- status
    status          TEXT NOT NULL DEFAULT 'disponivel', -- disponivel | reservado | vendido
    observacoes     TEXT,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_veiculos_empresa ON veiculos(empresa_id);
CREATE INDEX idx_veiculos_status  ON veiculos(empresa_id, status);
CREATE INDEX idx_veiculos_placa   ON veiculos(empresa_id, placa);

-- ============================================================
--  VENDAS
-- ============================================================
CREATE TABLE vendas (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id        UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    veiculo_id        UUID NOT NULL REFERENCES veiculos(id),
    cliente_id        UUID NOT NULL REFERENCES clientes(id),
    usuario_id        UUID REFERENCES usuarios(id),   -- quem registrou
    -- valores
    valor_venda       NUMERIC(12,2) NOT NULL,
    valor_entrada     NUMERIC(12,2) DEFAULT 0,
    desconto          NUMERIC(12,2) DEFAULT 0,
    -- pagamento
    forma_pagamento   TEXT NOT NULL, -- pix | cartao | boleto | financiamento | dinheiro | troca
    financeira        TEXT,
    parcelas          SMALLINT DEFAULT 1,
    -- datas
    data_venda        DATE NOT NULL DEFAULT CURRENT_DATE,
    data_registro     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- status
    status            TEXT NOT NULL DEFAULT 'concluida', -- concluida | cancelada | pendente
    observacoes       TEXT,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vendas_empresa   ON vendas(empresa_id);
CREATE INDEX idx_vendas_cliente   ON vendas(empresa_id, cliente_id);
CREATE INDEX idx_vendas_data      ON vendas(empresa_id, data_venda DESC);

-- ============================================================
--  PARCELAS A RECEBER
-- ============================================================
CREATE TABLE parcelas (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    venda_id        UUID NOT NULL REFERENCES vendas(id) ON DELETE CASCADE,
    cliente_id      UUID NOT NULL REFERENCES clientes(id),
    numero          SMALLINT NOT NULL,  -- 1, 2, 3...
    total           SMALLINT NOT NULL,  -- total de parcelas
    valor           NUMERIC(12,2) NOT NULL,
    data_vencimento DATE NOT NULL,
    data_pagamento  DATE,
    forma_pagamento TEXT,
    status          TEXT NOT NULL DEFAULT 'pendente', -- pendente | pago | vencido | cancelado
    observacoes     TEXT,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_parcelas_empresa    ON parcelas(empresa_id);
CREATE INDEX idx_parcelas_vencimento ON parcelas(empresa_id, data_vencimento);
CREATE INDEX idx_parcelas_status     ON parcelas(empresa_id, status);
CREATE INDEX idx_parcelas_cliente    ON parcelas(empresa_id, cliente_id);

-- ============================================================
--  CONTAS A PAGAR
-- ============================================================
CREATE TABLE contas_pagar (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    descricao       TEXT NOT NULL,
    categoria       TEXT NOT NULL DEFAULT 'outro', -- salario | aluguel | energia | agua | internet | combustivel | manutencao | imposto | outro
    valor           NUMERIC(12,2) NOT NULL,
    data_vencimento DATE NOT NULL,
    data_pagamento  DATE,
    forma_pagamento TEXT,
    recorrente      TEXT DEFAULT 'nao', -- nao | mensal | anual
    status          TEXT NOT NULL DEFAULT 'pendente', -- pendente | pago | vencido | cancelado
    observacoes     TEXT,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_contas_pagar_empresa    ON contas_pagar(empresa_id);
CREATE INDEX idx_contas_pagar_status     ON contas_pagar(empresa_id, status);
CREATE INDEX idx_contas_pagar_vencimento ON contas_pagar(empresa_id, data_vencimento);

-- ============================================================
--  CONFIGURAÇÕES DA EMPRESA
-- ============================================================
CREATE TABLE config_empresa (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE UNIQUE,
    -- APIs
    api_fipe        BOOLEAN DEFAULT TRUE,
    api_cep         BOOLEAN DEFAULT TRUE,
    api_placa       BOOLEAN DEFAULT FALSE,
    token_placa     TEXT,
    -- pagamentos conectados
    mercadopago_token   TEXT,
    pagseguro_token     TEXT,
    asaas_token         TEXT,
    bv_token            TEXT,
    -- config financeiro
    parcelas_max    SMALLINT DEFAULT 12,
    desconto_avista NUMERIC(5,2) DEFAULT 5.00,
    multa_atraso    NUMERIC(5,2) DEFAULT 2.00,
    financeira_nome TEXT,
    -- notificações
    whatsapp_ativo  BOOLEAN DEFAULT FALSE,
    whatsapp_token  TEXT,
    lembrete_dias   SMALLINT DEFAULT 3, -- dias antes do vencimento
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
--  VIEWS ÚTEIS
-- ============================================================

-- Dashboard: resumo financeiro do mês
CREATE OR REPLACE VIEW vw_resumo_mes AS
SELECT
    v.empresa_id,
    DATE_TRUNC('month', v.data_venda) AS mes,
    COUNT(*)                           AS total_vendas,
    SUM(v.valor_venda)                 AS receita_total,
    SUM(ve.preco_custo)                AS custo_total,
    SUM(v.valor_venda) - SUM(ve.preco_custo) AS lucro
FROM vendas v
JOIN veiculos ve ON v.veiculo_id = ve.id
WHERE v.status = 'concluida'
GROUP BY v.empresa_id, DATE_TRUNC('month', v.data_venda);

-- Parcelas em alerta (vencidas ou vencem em N dias)
CREATE OR REPLACE VIEW vw_parcelas_alerta AS
SELECT
    p.*,
    c.nome        AS cliente_nome,
    c.telefone    AS cliente_telefone,
    ve.marca      AS veiculo_marca,
    ve.modelo     AS veiculo_modelo,
    CURRENT_DATE - p.data_vencimento AS dias_atraso,
    p.data_vencimento - CURRENT_DATE AS dias_ate_vencer
FROM parcelas p
JOIN clientes c  ON p.cliente_id = c.id
JOIN vendas v    ON p.venda_id   = v.id
JOIN veiculos ve ON v.veiculo_id  = ve.id
WHERE p.status IN ('pendente','vencido')
  AND p.data_vencimento <= CURRENT_DATE + INTERVAL '7 days';

-- Estoque com margem
CREATE OR REPLACE VIEW vw_estoque_margem AS
SELECT
    ve.*,
    CASE WHEN ve.preco_venda > 0 AND ve.preco_custo > 0
         THEN ROUND(((ve.preco_venda - ve.preco_custo) / ve.preco_venda) * 100, 1)
         ELSE NULL
    END AS margem_pct,
    ve.preco_venda - ve.preco_custo AS lucro_previsto
FROM veiculos ve
WHERE ve.status != 'vendido';

-- ============================================================
--  FUNÇÃO: atualizar parcelas vencidas automaticamente
-- ============================================================
CREATE OR REPLACE FUNCTION fn_atualizar_vencidas()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE parcelas
    SET status = 'vencido', atualizado_em = NOW()
    WHERE status = 'pendente'
      AND data_vencimento < CURRENT_DATE;

    UPDATE contas_pagar
    SET status = 'vencido', atualizado_em = NOW()
    WHERE status = 'pendente'
      AND data_vencimento < CURRENT_DATE;
END;
$$;

-- ============================================================
--  TRIGGERS: atualizado_em automático
-- ============================================================
CREATE OR REPLACE FUNCTION fn_set_atualizado_em()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$;

DO $$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'empresas','usuarios','clientes','veiculos',
        'vendas','parcelas','contas_pagar','config_empresa'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER trg_%s_updated BEFORE UPDATE ON %s FOR EACH ROW EXECUTE FUNCTION fn_set_atualizado_em()',
            t, t
        );
    END LOOP;
END;
$$;

-- ============================================================
--  DADOS INICIAIS (seed)
-- ============================================================
INSERT INTO empresas (id, nome, cnpj, telefone, email, cidade, estado)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'JP Automóveis',
    '12345678000190',
    '85999990000',
    'contato@jpautomóveis.com.br',
    'Fortaleza', 'CE'
);

INSERT INTO usuarios (empresa_id, nome, email, senha_hash, perfil)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'João Pedro',
    'admin@jpautomóveis.com.br',
    -- senha: admin123  (bcrypt — troque em produção)
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMZJaaaSwm2G9dSwDsGNfIKQ5.',
    'proprietario'
);

INSERT INTO config_empresa (empresa_id, api_fipe, api_cep)
VALUES ('00000000-0000-0000-0000-000000000001', TRUE, TRUE);
