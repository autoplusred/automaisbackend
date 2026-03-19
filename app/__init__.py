from flask import Flask
from flask_cors import CORS
from .config import Config
from .db import init_db
from .routes.auth       import bp as auth_bp
from .routes.clientes   import bp as clientes_bp
from .routes.veiculos   import bp as veiculos_bp
from .routes.vendas     import bp as vendas_bp
from .routes.financeiro import bp as financeiro_bp
from .routes.dashboard  import bp as dashboard_bp
from .routes.config_empresa import bp as config_bp
from .routes.apis_externas  import bp as apis_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    init_db()

    app.register_blueprint(auth_bp,       url_prefix="/api/auth")
    app.register_blueprint(clientes_bp,   url_prefix="/api/clientes")
    app.register_blueprint(veiculos_bp,   url_prefix="/api/veiculos")
    app.register_blueprint(vendas_bp,     url_prefix="/api/vendas")
    app.register_blueprint(financeiro_bp, url_prefix="/api/financeiro")
    app.register_blueprint(dashboard_bp,  url_prefix="/api/dashboard")
    app.register_blueprint(config_bp,     url_prefix="/api/config")
    app.register_blueprint(apis_bp,       url_prefix="/api/ext")

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "automais-api"}

    return app
