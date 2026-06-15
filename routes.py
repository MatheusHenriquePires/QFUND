from fastapi import APIRouter
from fastapi.responses import FileResponse

from services.atividade_service import AtividadeService
from schemas import AtividadeRequest
from services.conteudos_service import (
    ConteudosService
)

conteudos_service = ConteudosService()
router = APIRouter()

service = AtividadeService()


@router.get("/disciplinas")
def listar_disciplinas():
    return service.disciplinas()


@router.get("/conteudos/{disciplina_id}")
def listar_conteudos(disciplina_id: str):
    return service.conteudos(disciplina_id)


@router.post("/gerar-atividade")
def gerar_atividade(request: AtividadeRequest):

    resultado = service.gerar(
        disciplina_id=request.disciplina_id,
        quantidade=request.quantidade,
        dificuldade=request.dificuldade,
        tipo=request.tipo,
        conteudo=request.conteudos,
        titulo=request.titulo
    )

    return FileResponse(
        resultado["arquivo"],
        media_type="application/pdf",
        filename="atividade.pdf"
    )