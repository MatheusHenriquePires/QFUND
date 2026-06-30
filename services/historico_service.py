from database import db


class HistoricoService:
    def add_record(self, user_id: int, tipo: str, arquivo: str, meta: dict, responsavel: str | None = None):
        return db.add_activity(user_id, tipo, arquivo, meta, responsavel)

    def list(self, user_id: int, tipo: str | None = None, responsavel: str | None = None):
        return db.list_activities(user_id, tipo, responsavel)

    def owns_file(self, user_id: int, arquivo: str):
        return db.activity_by_filename(user_id, arquivo)
