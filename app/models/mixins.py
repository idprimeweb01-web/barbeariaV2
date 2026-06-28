from flask import g
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import declared_attr


class TenantMixin:
    """Adiciona barbearia_id a qualquer model e fornece query_tenant() com isolamento automático."""

    @declared_attr
    def barbearia_id(cls):
        return Column(Integer, ForeignKey('barbearias.id'), nullable=False, index=True)

    @classmethod
    def query_tenant(cls):
        """Retorna query filtrada por g.barbearia_id.
        super_admin sem barbearia_id recebe query sem filtro (acesso cross-tenant).
        Qualquer outro perfil sem barbearia_id recebe query vazia (fail-safe, nunca fail-open)."""
        from app.extensions import db
        q = db.session.query(cls)
        barbearia_id = getattr(g, 'barbearia_id', None)
        if barbearia_id:
            q = q.filter(cls.barbearia_id == barbearia_id)
        elif getattr(g, 'perfil', None) != 'super_admin':
            q = q.filter(False)
        return q
