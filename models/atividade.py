from pydantic import BaseModel


class AtividadeRequest(BaseModel):

    disciplina: int

    quantidade: int = 10

    conteudo: str | None = None

    dificuldade: str | None = None

    tipo: str | None = None

    titulo: str = "Atividade de Revisão"

    professor: str = ""

    serie: str = ""