from flask import Blueprint, jsonify, g
from ..db import get_cursor
from ..middleware.auth import require_auth

bp = Blueprint("dashboard", __name__)


@bp.get("/")
@require_auth
def dashboard():
    with get_cursor() as cur:
        # KPIs gerais
        cur.execute(
            """SELECT
               (SELECT COUNT(*) FROM veiculos  WHERE empresa_id=%s AND status='disponivel')  AS estoque,
               (SELECT COUNT(*) FROM clientes  WHERE empresa_id=%s AND ativo=TRUE)            AS clientes,
               (SELECT COUNT(*) FROM vendas    WHERE empresa_id=%s AND status='concluida'
                  AND date_trunc('month',data_venda)=date_trunc('month',NOW()))               AS vendas_mes,
               (SELECT COALESCE(SUM(valor_venda),0) FROM vendas
                  WHERE empresa_id=%s AND status='concluida'
                  AND date_trunc('month',data_venda)=date_trunc('month',NOW()))               AS receita_mes,
               (SELECT COUNT(*) FROM parcelas  WHERE empresa_id=%s AND status='vencido')      AS parcelas_vencidas,
               (SELECT COALESCE(SUM(valor),0) FROM parcelas
                  WHERE empresa_id=%s AND status='vencido')                                    AS valor_vencido
            """,
            (g.empresa_id,) * 6,
        )
        kpis = dict(cur.fetchone())

        # atividade recente — últimas 10 ações (vendas + parcelas vencidas)
        cur.execute(
            """(SELECT 'venda' AS tipo,
                       ve.marca || ' ' || ve.modelo AS descricao,
                       c.nome AS detalhe,
                       v.valor_venda AS valor,
                       v.criado_em AS quando
                FROM vendas v
                JOIN clientes c  ON c.id = v.cliente_id
                JOIN veiculos ve ON ve.id = v.veiculo_id
                WHERE v.empresa_id=%s
                ORDER BY v.criado_em DESC LIMIT 5)
               UNION ALL
               (SELECT 'parcela_vencida',
                       c.nome,
                       ve.marca || ' ' || ve.modelo,
                       p.valor,
                       p.atualizado_em
                FROM parcelas p
                JOIN clientes c  ON c.id = p.cliente_id
                JOIN vendas   vd ON vd.id = p.venda_id
                JOIN veiculos ve ON ve.id = vd.veiculo_id
                WHERE p.empresa_id=%s AND p.status='vencido'
                ORDER BY p.data_vencimento LIMIT 5)
               ORDER BY quando DESC LIMIT 10""",
            (g.empresa_id, g.empresa_id),
        )
        atividade = [dict(r) for r in cur.fetchall()]

        # alertas
        cur.execute(
            "SELECT * FROM vw_parcelas_alerta WHERE empresa_id=%s ORDER BY data_vencimento LIMIT 20",
            (g.empresa_id,),
        )
        alertas = [dict(r) for r in cur.fetchall()]

    return jsonify({
        "kpis":      kpis,
        "atividade": atividade,
        "alertas":   alertas,
    })
