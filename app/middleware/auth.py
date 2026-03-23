import jwt
from functools import wraps
from flask import request, jsonify, current_app, g

def require_auth(f):
    """Valida JWT do Supabase e injeta g.usuario_id."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"erro": "Token ausente"}), 401

        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
                audience=current_app.config["SUPABASE_JWT_AUDIENCE"],
                issuer=f"{current_app.config['SUPABASE_URL']}/auth/v1" if current_app.config["SUPABASE_URL"] else None
            )
        except jwt.InvalidTokenError:
            try:
                payload = jwt.decode(
                    token,
                    current_app.config["JWT_SECRET"],
                    algorithms=["HS256"],
                    options={"verify_aud": False, "verify_iss": False}
                )
            except jwt.ExpiredSignatureError:
                return jsonify({"erro": "Token expirado"}), 401
            except jwt.InvalidTokenError as e:
                return jsonify({"erro": f"Token inválido: {str(e)}"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado"}), 401

        g.usuario_id = payload.get("sub")
        g.jwt_payload = payload
        app_meta = payload.get("app_metadata", {})
        user_meta = payload.get("user_metadata", {})
        g.empresa_id = user_meta.get("empresa_id") or app_meta.get("empresa_id") or payload.get("empresa_id")
        g.perfil = user_meta.get("perfil") or app_meta.get("perfil") or payload.get("perfil", "vendedor")

        if not g.usuario_id or not g.empresa_id:
            return jsonify({"erro": "Token sem dados de empresa/usuário"}), 401

        return f(*args, **kwargs)

    return wrapper

def require_perfil(*perfis):
    """Restringe a perfis específicos (após require_auth)."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if g.perfil not in perfis:
                return jsonify({"erro": "Sem permissão"}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator
