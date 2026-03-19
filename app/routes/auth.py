from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime, timedelta, timezone
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
