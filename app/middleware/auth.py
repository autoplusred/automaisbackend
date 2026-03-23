import jwt
from functools import wraps
from flask import request, jsonify, current_app, g

def _decode_supabase_token(token):
    supabase_url = current_app.config.get("SUPABASE_URL", "").rstrip("/")
    audience = current_app.config.get("SUPABASE_JWT_AUDIENCE", "authenticated")
    issuer = f"{supabase_url}/auth/v1" if supabase_url else None
    header = jwt.get_unverified_header(token) or {}
    alg = header.get("alg")

    if alg == "RS256":
        if not supabase_url:
            raise jwt.InvalidTokenError("SUPABASE_URL não configurada para validar token RS256")
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        jwk_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwk_client.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
        )

    if alg == "HS256" or not alg:
        try:
            return jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
                audience=audience,
                issuer=issuer if issuer else None,
                options={"verify_iss": bool(issuer)},
            )
        except jwt.InvalidTokenError:
            return jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
                options={"verify_aud": False, "verify_iss": False},
            )

    raise jwt.InvalidTokenError(f"Algoritmo JWT não suportado: {alg}")

def require_auth(f):
    """Valida JWT do Supabase e injeta g.usuario_id."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"erro": "Token ausente"}), 401

        token = auth.split(" ", 1)[1]
        try:
            payload = _decode_supabase_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"erro": f"Token inválido: {str(e)}"}), 401

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
