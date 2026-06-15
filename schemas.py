from pydantic import BaseModel
from typing import List, Optional


class AtividadeRequest(BaseModel):
    disciplina_id: str
    conteudos: Optional[List[int]] = []
    quantidade: int = 10
    dificuldade: Optional[str] = None
    tipo: Optional[str] = None
    incluir_gabarito: bool = False
    titulo: str = "Atividade"