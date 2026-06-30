from database import db

class UserService:
    def get_profile(self, user_id: int) -> dict:
        user = db.get_user(user_id)
        if not user:
            return {}
        return {
            "id": user["id"], "email": user["email"], "nome": user["name"],
            "tipo": user["role"], "disciplina_preferida": user["preferred_subject"],
        }

    def set_profile(self, user_id: int, profile: dict):
        current = db.get_user(user_id)
        if not current:
            raise ValueError("Usuário não encontrado")
        role = profile.get("tipo") or current["role"]
        if role not in ("professor", "usuario"):
            raise ValueError("Tipo de usuário inválido")
        name = profile.get("nome") or current["name"]
        db.update_user(user_id, name, role, profile.get("disciplina_preferida"))
