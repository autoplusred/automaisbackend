from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime, timedelta, timezone
from uuid import UUID
import bcrypt
import jwt
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("auth", __name__)


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    senha = data.get("senha") or ""

    if not email or not senha:
        return jsonify({"erro": "email e senha obrigatórios"}), 400

    with get_cursor() as cur:
        cur.execute(
            """SELECT u.id, u.empresa_id, u.nome, u.senha_hash, u.perfil, u.ativo,
                      e.nome AS empresa_nome
               FROM usuarios u
               JOIN empresas e ON e.id = u.empresa_id
               WHERE u.email = %s""",
            (email,),
        )
        user = cur.fetchone()

    if not user or not user["ativo"]:
        return jsonify({"erro": "Credenciais inválidas"}), 401

    if not bcrypt.checkpw(senha.encode(), user["senha_hash"].encode()):
        return jsonify({"erro": "Credenciais inválidas"}), 401

    expiry = datetime.now(timezone.utc) + timedelta(hours=current_app.config["JWT_EXPIRY_HOURS"])
    token = jwt.encode(
        {
            "sub":        str(user["id"]),
            "empresa_id": str(user["empresa_id"]),
            "perfil":     user["perfil"],
            "exp":        expiry,
        },
        current_app.config["JWT_SECRET"],
        algorithm="HS256",
    )

    # registra último login
    with get_cursor() as cur:
        cur.execute("UPDATE usuarios SET ultimo_login=NOW() WHERE id=%s", (user["id"],))

    return jsonify({
        "token":        token,
        "usuario": {
            "id":           str(user["id"]),
            "nome":         user["nome"],
            "perfil":       user["perfil"],
            "empresa_id":   str(user["empresa_id"]),
            "empresa_nome": user["empresa_nome"],
        },
    })


@bp.get("/me")
@require_auth
def me():
    with get_cursor() as cur:
        cur.execute(
            """SELECT u.id, u.nome, u.email, u.perfil, u.ultimo_login,
                      e.id AS empresa_id, e.nome AS empresa_nome
               FROM usuarios u JOIN empresas e ON e.id = u.empresa_id
               WHERE u.id = %s""",
            (g.usuario_id,),
        )
        user = cur.fetchone()
    if not user:
        return jsonify({"erro": "Usuário não encontrado"}), 404
    return jsonify(dict(user))


@bp.post("/trocar-senha")
@require_auth
def trocar_senha():
    data = request.get_json(silent=True) or {}
    senha_atual = data.get("senha_atual", "")
    nova_senha  = data.get("nova_senha", "")

    if len(nova_senha) < 6:
        return jsonify({"erro": "Nova senha deve ter ao menos 6 caracteres"}), 400

    with get_cursor() as cur:
        cur.execute("SELECT senha_hash FROM usuarios WHERE id=%s", (g.usuario_id,))
        row = cur.fetchone()

    if not row or not bcrypt.checkpw(senha_atual.encode(), row["senha_hash"].encode()):
        return jsonify({"erro": "Senha atual incorreta"}), 401

    novo_hash = bcrypt.hashpw(nova_senha.encode(), bcrypt.gensalt()).decode()
    with get_cursor() as cur:
        cur.execute("UPDATE usuarios SET senha_hash=%s WHERE id=%s", (novo_hash, g.usuario_id))

    return jsonify({"mensagem": "Senha atualizada"})


@bp.post("/bootstrap")
@require_auth
def bootstrap():
    d = request.get_json(silent=True) or {}
    payload = getattr(g, "jwt_payload", {}) or {}
    user_meta = payload.get("user_metadata", {}) or {}
    app_meta = payload.get("app_metadata", {}) or {}

    empresa_id = d.get("empresa_id") or g.empresa_id
    usuario_id = g.usuario_id
    email = (d.get("email") or payload.get("email") or "").strip().lower()
    nome_usuario = (d.get("nome") or user_meta.get("nome") or payload.get("name") or email.split("@")[0] or "Administrador").strip()
    perfil = d.get("perfil") or user_meta.get("perfil") or app_meta.get("perfil") or g.perfil or "proprietario"

    empresa_nome = (d.get("empresa_nome") or d.get("nome_loja") or user_meta.get("empresa_nome") or "Minha Concessionária").strip()
    cnpj = (d.get("cnpj") or user_meta.get("cnpj") or "").strip() or None
    telefone = (d.get("telefone") or user_meta.get("telefone") or "").strip() or None
    cidade = (d.get("cidade") or user_meta.get("cidade") or "").strip() or None
    estado = (d.get("estado") or user_meta.get("estado") or "").strip().upper() or None

    try:
        UUID(str(empresa_id))
        UUID(str(usuario_id))
    except Exception:
        return jsonify({"erro": "empresa_id ou usuário inválido"}), 400

    if not email:
        return jsonify({"erro": "Email do usuário não encontrado no token"}), 400

    with get_cursor() as cur:
        cur.execute("SELECT id FROM empresas WHERE id=%s", (str(empresa_id),))
        empresa_exists = cur.fetchone()

        if empresa_exists:
            cur.execute(
                """UPDATE empresas
                   SET nome=%s,
                       cnpj=COALESCE(%s, cnpj),
                       telefone=COALESCE(%s, telefone),
                       email=COALESCE(%s, email),
                       cidade=COALESCE(%s, cidade),
                       estado=COALESCE(%s, estado)
                   WHERE id=%s""",
                (empresa_nome, cnpj, telefone, email, cidade, estado, str(empresa_id)),
            )
        else:
            cur.execute(
                """INSERT INTO empresas
                   (id, nome, cnpj, telefone, email, cidade, estado)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (str(empresa_id), empresa_nome, cnpj, telefone, email, cidade, estado),
            )

        cur.execute("SELECT id FROM usuarios WHERE id=%s", (str(usuario_id),))
        usuario_exists = cur.fetchone()
        if usuario_exists:
            cur.execute(
                """UPDATE usuarios
                   SET empresa_id=%s, nome=%s, email=%s, perfil=%s, ativo=TRUE
                   WHERE id=%s""",
                (str(empresa_id), nome_usuario, email, perfil, str(usuario_id)),
            )
        else:
            cur.execute(
                """INSERT INTO usuarios (id, empresa_id, nome, email, senha_hash, perfil, ativo)
                   VALUES (%s,%s,%s,%s,%s,%s,TRUE)""",
                (str(usuario_id), str(empresa_id), nome_usuario, email, "", perfil),
            )

        cur.execute("SELECT id FROM config_empresa WHERE empresa_id=%s", (str(empresa_id),))
        cfg_exists = cur.fetchone()
        if not cfg_exists:
            cur.execute(
                "INSERT INTO config_empresa (empresa_id, api_fipe, api_cep) VALUES (%s, TRUE, TRUE)",
                (str(empresa_id),),
            )

    return jsonify({
        "mensagem": "Ambiente inicializado com sucesso",
        "empresa_id": str(empresa_id),
        "usuario_id": str(usuario_id),
    })
