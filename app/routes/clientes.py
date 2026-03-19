from flask import Blueprint, request, jsonify, g
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("clientes", __name__)


@bp.get("/")
@require_auth
def listar():
    q      = request.args.get("q", "")
    pagina = max(1, int(request.args.get("pagina", 1)))
    limite = min(100, int(request.args.get("limite", 50)))
    offset = (pagina - 1) * limite

    with get_cursor() as cur:
        if q:
            cur.execute(
                """SELECT * FROM clientes
                   WHERE empresa_id = %s AND ativo = TRUE
                     AND (nome ILIKE %s OR cpf ILIKE %s OR telefone ILIKE %s)
                   ORDER BY nome
                   LIMIT %s OFFSET %s""",
                (g.empresa_id, f"%{q}%", f"%{q}%", f"%{q}%", limite, offset),
            )
        else:
            cur.execute(
                "SELECT * FROM clientes WHERE empresa_id=%s AND ativo=TRUE ORDER BY nome LIMIT %s OFFSET %s",
                (g.empresa_id, limite, offset),
            )
        rows = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM clientes WHERE empresa_id=%s AND ativo=TRUE", (g.empresa_id,))
        total = cur.fetchone()["count"]

    return jsonify({"clientes": [dict(r) for r in rows], "total": total, "pagina": pagina})


@bp.get("/<uuid:id>")
@require_auth
def buscar(id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM clientes WHERE id=%s AND empresa_id=%s", (str(id), g.empresa_id))
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Não encontrado"}), 404
    return jsonify(dict(row))


@bp.get("/cpf/<cpf>")
@require_auth
def buscar_cpf(cpf):
    cpf_clean = cpf.replace(".", "").replace("-", "")
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM clientes WHERE empresa_id=%s AND replace(replace(cpf,'.',''),'-','')=%s",
            (g.empresa_id, cpf_clean),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"encontrado": False}), 404
    return jsonify({"encontrado": True, "cliente": dict(row)})


@bp.post("/")
@require_auth
def criar():
    d = request.get_json(silent=True) or {}
    if not d.get("nome"):
        return jsonify({"erro": "nome obrigatório"}), 400

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO clientes
               (empresa_id, nome, cpf, rg, cnh, data_nascimento, estado_civil,
                profissao, renda_mensal, telefone, telefone_fixo, email,
                cep, logradouro, numero, complemento, bairro, cidade, estado, observacoes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING *""",
            (
                g.empresa_id,
                d.get("nome"), d.get("cpf"), d.get("rg"), d.get("cnh"),
                d.get("data_nascimento") or None, d.get("estado_civil"),
                d.get("profissao"), d.get("renda_mensal"),
                d.get("telefone"), d.get("telefone_fixo"), d.get("email"),
                d.get("cep"), d.get("logradouro"), d.get("numero"),
                d.get("complemento"), d.get("bairro"), d.get("cidade"),
                d.get("estado"), d.get("observacoes"),
            ),
        )
        novo = cur.fetchone()

    return jsonify(dict(novo)), 201


@bp.put("/<uuid:id>")
@require_auth
def atualizar(id):
    d = request.get_json(silent=True) or {}
    with get_cursor() as cur:
        cur.execute(
            """UPDATE clientes SET
               nome=%s, cpf=%s, rg=%s, cnh=%s, data_nascimento=%s, estado_civil=%s,
               profissao=%s, renda_mensal=%s, telefone=%s, telefone_fixo=%s, email=%s,
               cep=%s, logradouro=%s, numero=%s, complemento=%s, bairro=%s,
               cidade=%s, estado=%s, observacoes=%s
               WHERE id=%s AND empresa_id=%s RETURNING *""",
            (
                d.get("nome"), d.get("cpf"), d.get("rg"), d.get("cnh"),
                d.get("data_nascimento") or None, d.get("estado_civil"),
                d.get("profissao"), d.get("renda_mensal"),
                d.get("telefone"), d.get("telefone_fixo"), d.get("email"),
                d.get("cep"), d.get("logradouro"), d.get("numero"),
                d.get("complemento"), d.get("bairro"), d.get("cidade"),
                d.get("estado"), d.get("observacoes"),
                str(id), g.empresa_id,
            ),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Não encontrado"}), 404
    return jsonify(dict(row))


@bp.delete("/<uuid:id>")
@require_auth
def deletar(id):
    with get_cursor() as cur:
        cur.execute(
            "UPDATE clientes SET ativo=FALSE WHERE id=%s AND empresa_id=%s RETURNING id",
            (str(id), g.empresa_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Não encontrado"}), 404
    return jsonify({"mensagem": "Removido"})
