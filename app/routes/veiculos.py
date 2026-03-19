from flask import Blueprint, request, jsonify, g
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("veiculos", __name__)


@bp.get("/")
@require_auth
def listar():
    status = request.args.get("status")   # disponivel|reservado|vendido
    tipo   = request.args.get("tipo")
    q      = request.args.get("q", "")
    pagina = max(1, int(request.args.get("pagina", 1)))
    limite = min(100, int(request.args.get("limite", 50)))
    offset = (pagina - 1) * limite

    filtros = ["empresa_id = %s"]
    params  = [g.empresa_id]

    if status:
        filtros.append("status = %s"); params.append(status)
    if tipo:
        filtros.append("tipo = %s"); params.append(tipo)
    if q:
        filtros.append("(marca ILIKE %s OR modelo ILIKE %s OR placa ILIKE %s)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]

    where = " AND ".join(filtros)

    with get_cursor() as cur:
        cur.execute(
            f"SELECT * FROM vw_estoque_margem WHERE {where} ORDER BY criado_em DESC LIMIT %s OFFSET %s",
            params + [limite, offset],
        )
        rows = cur.fetchall()
        cur.execute(f"SELECT COUNT(*) FROM veiculos WHERE {where}", params)
        total = cur.fetchone()["count"]

    return jsonify({"veiculos": [dict(r) for r in rows], "total": total})


@bp.get("/<uuid:id>")
@require_auth
def buscar(id):
    with get_cursor() as cur:
        cur.execute("SELECT * FROM veiculos WHERE id=%s AND empresa_id=%s", (str(id), g.empresa_id))
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Não encontrado"}), 404
    return jsonify(dict(row))


@bp.post("/")
@require_auth
def criar():
    d = request.get_json(silent=True) or {}
    if not d.get("marca") or not d.get("modelo"):
        return jsonify({"erro": "marca e modelo obrigatórios"}), 400

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO veiculos
               (empresa_id, placa, renavam, chassi,
                fipe_codigo, fipe_marca, fipe_marca_cod, fipe_modelo,
                fipe_modelo_cod, fipe_ano_cod, fipe_preco, fipe_referencia,
                marca, modelo, versao, tipo, ano_fabricacao, ano_modelo,
                km, cor, combustivel, cambio, preco_custo, preco_venda, observacoes)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               RETURNING *""",
            (
                g.empresa_id,
                d.get("placa"), d.get("renavam"), d.get("chassi"),
                d.get("fipe_codigo"), d.get("fipe_marca"), d.get("fipe_marca_cod"),
                d.get("fipe_modelo"), d.get("fipe_modelo_cod"), d.get("fipe_ano_cod"),
                d.get("fipe_preco"), d.get("fipe_referencia"),
                d["marca"], d["modelo"], d.get("versao"), d.get("tipo"),
                d.get("ano_fabricacao"), d.get("ano_modelo"),
                d.get("km"), d.get("cor"), d.get("combustivel"), d.get("cambio"),
                d.get("preco_custo"), d.get("preco_venda"), d.get("observacoes"),
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
            """UPDATE veiculos SET
               placa=%s, renavam=%s, chassi=%s,
               fipe_codigo=%s, fipe_marca=%s, fipe_preco=%s, fipe_referencia=%s,
               marca=%s, modelo=%s, versao=%s, tipo=%s,
               ano_fabricacao=%s, ano_modelo=%s, km=%s, cor=%s,
               combustivel=%s, cambio=%s,
               preco_custo=%s, preco_venda=%s, status=%s, observacoes=%s
               WHERE id=%s AND empresa_id=%s RETURNING *""",
            (
                d.get("placa"), d.get("renavam"), d.get("chassi"),
                d.get("fipe_codigo"), d.get("fipe_marca"),
                d.get("fipe_preco"), d.get("fipe_referencia"),
                d.get("marca"), d.get("modelo"), d.get("versao"), d.get("tipo"),
                d.get("ano_fabricacao"), d.get("ano_modelo"), d.get("km"),
                d.get("cor"), d.get("combustivel"), d.get("cambio"),
                d.get("preco_custo"), d.get("preco_venda"),
                d.get("status", "disponivel"), d.get("observacoes"),
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
            "DELETE FROM veiculos WHERE id=%s AND empresa_id=%s AND status='disponivel' RETURNING id",
            (str(id), g.empresa_id),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Não encontrado ou já vendido"}), 400
    return jsonify({"mensagem": "Removido"})
