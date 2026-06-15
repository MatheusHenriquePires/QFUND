from pydantic import BaseModel


class Questao(BaseModel):

    id: int

    tipo: str

    enunciado: str

    alternativas: list[str]

    gabarito: str | None = None

    resolucao: str | None = None

    conteudo: str | None = None

    dificuldade: str | None = None

    ano: str | None = None

    origem: str | None = None