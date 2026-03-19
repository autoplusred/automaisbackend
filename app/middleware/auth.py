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
            # O JWT_SECRET no backend DEVE ser o JWT Secret do Supabase (Configurações > API > JWT Secret)
            # A audiência padrão do Supabase é "authenticated"
            payload = jwt.decode(
                token,
                current_app.config["JWT_SECRET"],
                algorithms=["HS256"],
                audience="authenticated"
            )
        except jwt.ExpiredSignatureError:
            return jsonify({"erro": "Token expirado"}), 401
        except jwt.InvalidTokenError as e:
            return jsonify({"erro": f"Token inválido: {str(e)}"}), 401

        # O 'sub' no JWT do Supabase é o UUID do usuário
        g.usuario_id = payload.get("sub")
        
        # Metadados adicionais (como perfil ou empresa) ficam em app_metadata ou user_metadata
        user_meta = payload.get("user_metadata", {})
        g.empresa_id = user_meta.get("empresa_id", None)
        g.perfil     = user_meta.get("perfil", "vendedor")
        
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
