from flask import Blueprint, request, jsonify, g
from datetime import date
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("financeiro", __name__)


# ── Parcelas a receber ─────────────────────────────────────────

@bp.get("/parcelas")
@require_auth
def listar_parcelas():
    status  = request.args.get("status")
    alertas = request.args.get("alertas")  # ?alertas=1 → só vencidas/proximas
    pagina  = max(1, int(request.args.get("pagina", 1)))
    limite  = min(200, int(request.args.get("limite", 50)))
    offset  = (pagina - 1) * limite

    if alertas:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM vw_parcelas_alerta WHERE empresa_id=%s ORDER BY data_vencimento",
                (g.empresa_id,),
            )
            rows = cur.fetchall()
        return jsonify({"parcelas": [dict(r) for r in rows]})

    filtros = ["p.empresa_id=%s"]
    params  = [g.empresa_id]
    if status:
        filtros.append("p.status=%s"); params.append(status)

    where = " AND ".join(filtros)
    with get_cursor() as cur:
        cur.execute(
            f"""SELECT p.*, c.nome AS cliente_nome,
                       ve.marca || ' ' || ve.modelo AS veiculo
                FROM parcelas p
                JOIN clientes c  ON c.id = p.cliente_id
                JOIN vendas   v  ON v.id = p.venda_id
                JOIN veiculos ve ON ve.id = v.veiculo_id
                WHERE {where}
                ORDER BY p.data_vencimento
                LIMIT %s OFFSET %s""",
            params + [limite, offset],
        )
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) FROM parcelas p WHERE {where}", params)
        total = cur.fetchone()["count"]

    return jsonify({"parcelas": [dict(r) for r in rows], "total": total})


@bp.post("/parcelas/<uuid:id>/receber")
@require_auth
def receber_parcela(id):
    d = request.get_json(silent=True) or {}
    data_pgto = d.get("data_pagamento") or date.today().isoformat()
    forma     = d.get("forma_pagamento", "pix")
    obs       = d.get("observacoes", "")

    with get_cursor() as cur:
        cur.execute(
            """UPDATE parcelas SET
               status='pago', data_pagamento=%s,
               forma_pagamento=%s, observacoes=%s
               WHERE id=%s AND empresa_id=%s AND status IN ('pendente','vencido')
               RETURNING *""",
            (data_pgto, forma, obs, str(id), g.empresa_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Parcela não encontrada ou já paga"}), 400
    return jsonify(dict(row))


# ── Contas a pagar ─────────────────────────────────────────────

@bp.get("/contas")
@require_auth
def listar_contas():
    status     = request.args.get("status")
    categoria  = request.args.get("categoria")
    pagina     = max(1, int(request.args.get("pagina", 1)))
    limite     = min(200, int(request.args.get("limite", 50)))
    offset     = (pagina - 1) * limite

    # atualiza vencidas antes de retornar
    with get_cursor() as cur:
        cur.execute(
            """UPDATE contas_pagar SET status='vencido'
               WHERE empresa_id=%s AND status='pendente'
                 AND data_vencimento < CURRENT_DATE""",
            (g.empresa_id,),
        )

    filtros = ["empresa_id=%s"]
    params  = [g.empresa_id]
    if status:    filtros.append("status=%s");    params.append(status)
    if categoria: filtros.append("categoria=%s"); params.append(categoria)

    where = " AND ".join(filtros)
    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM contas_pagar WHERE {where} ORDER BY data_vencimento LIMIT %s OFFSET %s",
            params + [limite, offset],
        )
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) FROM contas_pagar WHERE {where}", params)
        total = cur.fetchone()["count"]

    return jsonify({"contas": [dict(r) for r in rows], "total": total})


@bp.post("/contas")
@require_auth
def criar_conta():
    d = request.get_json(silent=True) or {}
    if not d.get("descricao") or not d.get("valor") or not d.get("data_vencimento"):
        return jsonify({"erro": "descricao, valor e data_vencimento obrigatórios"}), 400

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO contas_pagar
               (empresa_id, descricao, categoria, valor, data_vencimento,
                recorrente, forma_pagamento, observacoes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
            (
                g.empresa_id, d["descricao"],
                d.get("categoria", "outro"), d["valor"],
                d["data_vencimento"], d.get("recorrente", "nao"),
                d.get("forma_pagamento"), d.get("observacoes"),
            ),
        )
        nova = cur.fetchone()

    return jsonify(dict(nova)), 201


@bp.post("/contas/<uuid:id>/pagar")
@require_auth
def pagar_conta(id):
    d = request.get_json(silent=True) or {}
    data_pgto = d.get("data_pagamento") or date.today().isoformat()
    forma     = d.get("forma_pagamento", "pix")

    with get_cursor() as cur:
        cur.execute(
            """UPDATE contas_pagar SET
               status='pago', data_pagamento=%s, forma_pagamento=%s
               WHERE id=%s AND empresa_id=%s AND status IN ('pendente','vencido')
               RETURNING *""",
            (data_pgto, forma, str(id), g.empresa_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Conta não encontrada ou já paga"}), 400
    return jsonify(dict(row))


@bp.delete("/contas/<uuid:id>")
@require_auth
def deletar_conta(id):
    with get_cursor() as cur:
        cur.execute(
            "DELETE FROM contas_pagar WHERE id=%s AND empresa_id=%s RETURNING id",
            (str(id), g.empresa_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Não encontrado"}), 404
    return jsonify({"mensagem": "Removido"})


# ── Resumo financeiro ──────────────────────────────────────────

@bp.get("/resumo")
@require_auth
def resumo():
    with get_cursor() as cur:
        # a receber total e vencido
        cur.execute(
            """SELECT
               SUM(valor) FILTER (WHERE status IN ('pendente','vencido')) AS total_receber,
               SUM(valor) FILTER (WHERE status = 'vencido')              AS total_vencido,
               SUM(valor) FILTER (WHERE status = 'pago'
                 AND date_trunc('month', data_pagamento) = date_trunc('month', NOW())) AS recebido_mes
               FROM parcelas WHERE empresa_id=%s""",
            (g.empresa_id,),
        )
        rec = cur.fetchone()

        # a pagar
        cur.execute(
            """SELECT
               SUM(valor) FILTER (WHERE status IN ('pendente','vencido')) AS total_pagar,
               SUM(valor) FILTER (WHERE status = 'pago'
                 AND date_trunc('month', data_pagamento) = date_trunc('month', NOW())) AS pago_mes
               FROM contas_pagar WHERE empresa_id=%s""",
            (g.empresa_id,),
        )
        pag = cur.fetchone()

        # vendas mês atual
        cur.execute(
            """SELECT COUNT(*) AS qtd, SUM(valor_venda) AS receita
               FROM vendas
               WHERE empresa_id=%s AND status='concluida'
                 AND date_trunc('month', data_venda) = date_trunc('month', NOW())""",
            (g.empresa_id,),
        )
        vendas = cur.fetchone()

        # estoque
        cur.execute(
            "SELECT COUNT(*) AS total, SUM(preco_custo) AS custo FROM veiculos WHERE empresa_id=%s AND status='disponivel'",
            (g.empresa_id,),
        )
        estoque = cur.fetchone()

    return jsonify({
        "a_receber": {
            "total":   float(rec["total_receber"] or 0),
            "vencido": float(rec["total_vencido"] or 0),
            "recebido_mes": float(rec["recebido_mes"] or 0),
        },
        "a_pagar": {
            "total":    float(pag["total_pagar"] or 0),
            "pago_mes": float(pag["pago_mes"] or 0),
        },
        "vendas_mes": {
            "quantidade": int(vendas["qtd"] or 0),
            "receita":    float(vendas["receita"] or 0),
        },
        "estoque": {
            "veiculos": int(estoque["total"] or 0),
            "custo":    float(estoque["custo"] or 0),
        },
    })
