from flask import Blueprint, request, jsonify, g
from ..db import get_cursor
from ..middleware.auth import require_auth, require_perfil

bp = Blueprint("config_empresa", __name__)


@bp.get("/")
@require_auth
def get_config():
    with get_cursor() as cur:
        cur.execute(
            """SELECT c.*, e.nome AS empresa_nome, e.cnpj, e.telefone,
                      e.email, e.cep, e.logradouro, e.numero,
                      e.bairro, e.cidade, e.estado
               FROM config_empresa c
               JOIN empresas e ON e.id = c.empresa_id
               WHERE c.empresa_id=%s""",
            (g.empresa_id,),
        )
        row = cur.fetchone()
    if not row:
        return jsonify({"erro": "Config não encontrada"}), 404

    # oculta tokens sensíveis — retorna apenas se existem
    data = dict(row)
    for k in ("token_placa","mercadopago_token","pagseguro_token","asaas_token","bv_token","whatsapp_token"):
        if data.get(k):
            data[k] = "***configurado***"
    return jsonify(data)


@bp.put("/")
@require_auth
@require_perfil("proprietario", "gerente")
def atualizar_config():
    d = request.get_json(silent=True) or {}

    # campos da empresa
    campos_empresa = ["nome","cnpj","telefone","email","cep","logradouro","numero","bairro","cidade","estado"]
    empresa_updates = {k: d[k] for k in campos_empresa if k in d}

    # campos de config
    campos_config = [
        "api_fipe","api_cep","api_placa",
        "mercadopago_token","pagseguro_token","asaas_token","bv_token",
        "parcelas_max","desconto_avista","multa_atraso","financeira_nome",
        "whatsapp_ativo","whatsapp_token","lembrete_dias",
    ]
    # token_placa: só atualiza se vier explícito (não "***configurado***")
    if d.get("token_placa") and d["token_placa"] != "***configurado***":
        campos_config.append("token_placa")

    config_updates = {k: d[k] for k in campos_config if k in d}

    with get_cursor() as cur:
        if empresa_updates:
            sets = ", ".join(f"{k}=%s" for k in empresa_updates)
            cur.execute(
                f"UPDATE empresas SET {sets} WHERE id=%s",
                list(empresa_updates.values()) + [g.empresa_id],
            )

        if config_updates:
            sets = ", ".join(f"{k}=%s" for k in config_updates)
            cur.execute(
                f"UPDATE config_empresa SET {sets} WHERE empresa_id=%s",
                list(config_updates.values()) + [g.empresa_id],
            )

    return jsonify({"mensagem": "Configurações atualizadas"})


@bp.put("/api-toggle")
@require_auth
@require_perfil("proprietario", "gerente")
def toggle_api():
    """Liga/desliga uma API específica: { "api": "fipe"|"cep"|"placa", "ativo": true|false }"""
    d = request.get_json(silent=True) or {}
    api = d.get("api")
    ativo = d.get("ativo")

    mapa = {"fipe": "api_fipe", "cep": "api_cep", "placa": "api_placa"}
    if api not in mapa or ativo is None:
        return jsonify({"erro": "api e ativo obrigatórios"}), 400

    campo = mapa[api]
    with get_cursor() as cur:
        cur.execute(
            f"UPDATE config_empresa SET {campo}=%s WHERE empresa_id=%s",
            (bool(ativo), g.empresa_id),
        )
    return jsonify({"mensagem": f"{api} {'ligado' if ativo else 'desligado'}"})
