"""
Proxy para APIs externas — o frontend chama o backend,
que verifica se a API está habilitada para a empresa e
faz a chamada real. Evita expor tokens no frontend.
"""
import requests
from flask import Blueprint, request, jsonify, g
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("apis_externas", __name__)

BRASIL_API   = "https://brasilapi.com.br/api"
PARALLELUM   = "https://parallelum.com.br/fipe/api/v2"
FIPEAPI_BASE = "https://fipeapi.com.br/api/v1"


def _config(cur, empresa_id):
    cur.execute("SELECT * FROM config_empresa WHERE empresa_id=%s", (empresa_id,))
    return cur.fetchone() or {}


# ── CEP ───────────────────────────────────────────────────────

@bp.get("/cep/<cep>")
@require_auth
def cep(cep):
    with get_cursor() as cur:
        cfg = _config(cur, g.empresa_id)

    if not cfg.get("api_cep"):
        return jsonify({"erro": "API de CEP desabilitada nas configurações"}), 403

    try:
        r = requests.get(f"{BRASIL_API}/cep/v2/{cep}", timeout=5)
        r.raise_for_status()
        return jsonify(r.json())
    except requests.HTTPError:
        return jsonify({"erro": "CEP não encontrado"}), 404
    except Exception as e:
        return jsonify({"erro": str(e)}), 502


# ── FIPE ──────────────────────────────────────────────────────

TIPO_MAP = {"carros": "cars", "motos": "motorcycles", "caminhoes": "trucks"}


@bp.get("/fipe/marcas/<tipo>")
@require_auth
def fipe_marcas(tipo):
    with get_cursor() as cur:
        cfg = _config(cur, g.empresa_id)
    if not cfg.get("api_fipe"):
        return jsonify({"erro": "API FIPE desabilitada"}), 403

    t = TIPO_MAP.get(tipo, "cars")
    try:
        r = requests.get(f"{PARALLELUM}/{t}/brands", timeout=8)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"erro": str(e)}), 502


@bp.get("/fipe/marcas/<tipo>/<marca_cod>/modelos")
@require_auth
def fipe_modelos(tipo, marca_cod):
    with get_cursor() as cur:
        cfg = _config(cur, g.empresa_id)
    if not cfg.get("api_fipe"):
        return jsonify({"erro": "API FIPE desabilitada"}), 403

    t = TIPO_MAP.get(tipo, "cars")
    try:
        r = requests.get(f"{PARALLELUM}/{t}/brands/{marca_cod}/models", timeout=8)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"erro": str(e)}), 502


@bp.get("/fipe/marcas/<tipo>/<marca_cod>/modelos/<modelo_cod>/anos")
@require_auth
def fipe_anos(tipo, marca_cod, modelo_cod):
    with get_cursor() as cur:
        cfg = _config(cur, g.empresa_id)
    if not cfg.get("api_fipe"):
        return jsonify({"erro": "API FIPE desabilitada"}), 403

    t = TIPO_MAP.get(tipo, "cars")
    try:
        r = requests.get(f"{PARALLELUM}/{t}/brands/{marca_cod}/models/{modelo_cod}/years", timeout=8)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"erro": str(e)}), 502


@bp.get("/fipe/marcas/<tipo>/<marca_cod>/modelos/<modelo_cod>/anos/<ano_cod>/preco")
@require_auth
def fipe_preco(tipo, marca_cod, modelo_cod, ano_cod):
    with get_cursor() as cur:
        cfg = _config(cur, g.empresa_id)
    if not cfg.get("api_fipe"):
        return jsonify({"erro": "API FIPE desabilitada"}), 403

    t = TIPO_MAP.get(tipo, "cars")
    try:
        r = requests.get(f"{PARALLELUM}/{t}/brands/{marca_cod}/models/{modelo_cod}/years/{ano_cod}", timeout=8)
        r.raise_for_status()
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"erro": str(e)}), 502


# ── Placa ─────────────────────────────────────────────────────

@bp.get("/placa/<placa>")
@require_auth
def consulta_placa(placa):
    with get_cursor() as cur:
        cfg = _config(cur, g.empresa_id)

    if not cfg.get("api_placa"):
        return jsonify({"erro": "API de placa desabilitada nas configurações"}), 403

    token = cfg.get("token_placa")
    if not token:
        return jsonify({"erro": "Token da API de placa não configurado"}), 400

    clean = placa.upper().replace("-", "")
    try:
        r = requests.get(
            f"{FIPEAPI_BASE}/placa/{clean}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=8,
        )
        r.raise_for_status()
        return jsonify(r.json())
    except requests.HTTPError as e:
        return jsonify({"erro": f"Placa não encontrada ({e.response.status_code})"}), e.response.status_code
    except Exception as e:
        return jsonify({"erro": str(e)}), 502
