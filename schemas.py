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
    serie: Optional[str] = None  # ex: "EF6", "EM1"


class PreviewActionRequest(BaseModel):
    preview_id: str
    questao_id: Union[str, int]
    tipo: Optional[str] = None


class PreviewQuestionCreateRequest(BaseModel):
    preview_id: str
    tipo: str
    enunciado: str
    alternativas: Optional[List[str]] = []
    gabarito: Optional[str] = None
    conteudo: Optional[str] = None
    dificuldade: Optional[str] = None


class PreviewGenerateRequest(BaseModel):
    preview_id: str


class UserProfile(BaseModel):
    nome: Optional[str] = None
    tipo: Optional[str] = "usuario"  # 'professor' ou 'usuario'
    disciplina_preferida: Optional[str] = None

