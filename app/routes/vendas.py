from flask import Blueprint, request, jsonify, g
from datetime import date
from dateutil.relativedelta import relativedelta
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("vendas", __name__)


def _gerar_parcelas(cur, venda_id, empresa_id, cliente_id, valor_venda,
                    valor_entrada, parcelas, data_venda):
    """Gera as linhas de parcelas para uma venda parcelada/a prazo."""
    if parcelas <= 1 and valor_entrada >= valor_venda:
        # pagamento à vista total — cria parcela única já paga
        cur.execute(
            """INSERT INTO parcelas
               (empresa_id, venda_id, cliente_id, numero, total, valor,
                data_vencimento, data_pagamento, status)
               VALUES (%s,%s,%s,1,1,%s,%s,%s,'pago')""",
            (empresa_id, venda_id, cliente_id,
             valor_venda, data_venda, data_venda),
        )
        return

    saldo = float(valor_venda) - float(valor_entrada or 0)
    if parcelas < 1:
        parcelas = 1
    valor_parcela = round(saldo / parcelas, 2)

    for i in range(1, parcelas + 1):
        vencimento = data_venda + relativedelta(months=i)
        cur.execute(
            """INSERT INTO parcelas
               (empresa_id, venda_id, cliente_id, numero, total, valor, data_vencimento)
               VALUES (%s,%s,%s,%s,%s,%s,%s)""",
            (empresa_id, venda_id, cliente_id, i, parcelas, valor_parcela, vencimento),
        )


@bp.get("/")
@require_auth
def listar():
    pagina = max(1, int(request.args.get("pagina", 1)))
    limite = min(100, int(request.args.get("limite", 50)))
    offset = (pagina - 1) * limite

    with get_cursor() as cur:
        cur.execute(
            """SELECT v.*, c.nome AS cliente_nome, ve.modelo AS veiculo_modelo,
                      ve.marca AS veiculo_marca, ve.placa AS veiculo_placa
               FROM vendas v
               JOIN clientes c  ON c.id = v.cliente_id
               JOIN veiculos ve ON ve.id = v.veiculo_id
               WHERE v.empresa_id = %s
               ORDER BY v.data_venda DESC, v.criado_em DESC
               LIMIT %s OFFSET %s""",
            (g.empresa_id, limite, offset),
        )
        rows = cur.fetchall()
        cur.execute("SELECT COUNT(*) FROM vendas WHERE empresa_id=%s", (g.empresa_id,))
        total = cur.fetchone()["count"]

    return jsonify({"vendas": [dict(r) for r in rows], "total": total})


@bp.get("/<uuid:id>")
@require_auth
def buscar(id):
    with get_cursor() as cur:
        cur.execute(
            """SELECT v.*, c.nome AS cliente_nome, ve.modelo AS veiculo_modelo,
                      ve.marca AS veiculo_marca, ve.placa AS veiculo_placa
               FROM vendas v
               JOIN clientes c  ON c.id = v.cliente_id
               JOIN veiculos ve ON ve.id = v.veiculo_id
               WHERE v.id=%s AND v.empresa_id=%s""",
            (str(id), g.empresa_id),
        )
        venda = cur.fetchone()
        if not venda:
            return jsonify({"erro": "Não encontrado"}), 404

        cur.execute(
            "SELECT * FROM parcelas WHERE venda_id=%s ORDER BY numero",
            (str(id),),
        )
        parcelas = cur.fetchall()

    return jsonify({**dict(venda), "parcelas": [dict(p) for p in parcelas]})


@bp.post("/")
@require_auth
def criar():
    d = request.get_json(silent=True) or {}

    required = ["veiculo_id", "cliente_id", "valor_venda", "forma_pagamento"]
    for f_ in required:
        if not d.get(f_):
            return jsonify({"erro": f"{f_} obrigatório"}), 400

    data_venda_str = d.get("data_venda")
    try:
        data_venda = (
            date.fromisoformat(data_venda_str)
            if data_venda_str
            else date.today()
        )
    except ValueError:
        return jsonify({"erro": "data_venda inválida (YYYY-MM-DD)"}), 400

    parcelas_n = int(d.get("parcelas", 1))

    with get_cursor() as cur:
        # verifica se veículo pertence à empresa e está disponível
        cur.execute(
            "SELECT id FROM veiculos WHERE id=%s AND empresa_id=%s AND status='disponivel'",
            (d["veiculo_id"], g.empresa_id),
        )
        if not cur.fetchone():
            return jsonify({"erro": "Veículo indisponível"}), 400

        # cria venda
        cur.execute(
            """INSERT INTO vendas
               (empresa_id, veiculo_id, cliente_id, usuario_id,
                valor_venda, valor_entrada, desconto,
                forma_pagamento, financeira, parcelas,
                data_venda, status, observacoes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING *""",
            (
                g.empresa_id, d["veiculo_id"], d["cliente_id"], g.usuario_id,
                d["valor_venda"], d.get("valor_entrada", 0), d.get("desconto", 0),
                d["forma_pagamento"], d.get("financeira"),
                parcelas_n, data_venda,
                d.get("status", "concluida"), d.get("observacoes"),
            ),
        )
        venda = cur.fetchone()

        # marca veículo como vendido
        cur.execute(
            "UPDATE veiculos SET status='vendido' WHERE id=%s",
            (d["veiculo_id"],),
        )

        # gera parcelas
        _gerar_parcelas(
            cur,
            venda["id"], g.empresa_id, d["cliente_id"],
            d["valor_venda"], d.get("valor_entrada", 0),
            parcelas_n, data_venda,
        )

    return jsonify(dict(venda)), 201


@bp.delete("/<uuid:id>")
@require_auth
def cancelar(id):
    with get_cursor() as cur:
        cur.execute(
            """UPDATE vendas SET status='cancelada'
               WHERE id=%s AND empresa_id=%s AND status!='cancelada'
               RETURNING veiculo_id""",
            (str(id), g.empresa_id),
        )
        row = cur.fetchone()
        if not row:
            return jsonify({"erro": "Venda não encontrada ou já cancelada"}), 400

        # devolve veículo ao estoque
        cur.execute(
            "UPDATE veiculos SET status='disponivel' WHERE id=%s",
            (row["veiculo_id"],),
        )
        # cancela parcelas pendentes
        cur.execute(
            "UPDATE parcelas SET status='cancelado' WHERE venda_id=%s AND status='pendente'",
            (str(id),),
        )

    return jsonify({"mensagem": "Venda cancelada"})
