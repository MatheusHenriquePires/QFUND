from pydantic import BaseModel
from typing import List, Optional, Union


class AtividadeRequest(BaseModel):
    disciplina_id: str
    conteudos: Optional[List[Union[str, int]]] = []
    quantidade: int = 10
    dificuldade: Optional[str] = None
    tipo: Optional[str] = None
    incluir_gabarito: bool = False
    titulo: str = "Atividade"
    tipo_usuario: Optional[str] = None
    professor: Optional[str] = None
    data_avaliacao: Optional[str] = None


class UserProfile(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = "usuario"  # 'professor' ou 'usuario'
    disciplina_preferida: Optional[str] = None
