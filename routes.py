import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from services.atividade_service import AtividadeService
from schemas import AtividadeRequest, PreviewActionRequest, PreviewGenerateRequest, UserProfile
from services.conteudos_service import ConteudosService
from services.historico_service import HistoricoService
from services.user_service import UserService


conteudos_service = ConteudosService()
router = APIRouter()
logger = logging.getLogger("qfund.routes")

service = AtividadeService()
historico_service = HistoricoService()
user_service = UserService()

@router.get("/disciplinas")
def listar_disciplinas():
    resposta = service.disciplinas()
    disciplinas = resposta.get("data", []) if isinstance(resposta, dict) else resposta

    return {
        "data": [
            {
                "id": disciplina.get("id"),
                "name": disciplina.get("name")
            }
            for disciplina in disciplinas
        ]
    }


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
        titulo=request.titulo,
        incluir_gabarito=request.incluir_gabarito,
        professor=request.professor,
        data_avaliacao=request.data_avaliacao,
        serie=request.serie
    )

    arquivo = resultado.get("arquivo")
    if not arquivo:
        raise HTTPException(status_code=500, detail="Erro ao gerar arquivo")

    # salvar histórico (salva apenas o nome do arquivo), associando tipo/resp
    try:
        nome_arquivo = Path(arquivo).name
        meta = {
            "disciplina_id": request.disciplina_id,
            "quantidade": request.quantidade,
            "dificuldade": request.dificuldade,
            "tipo": request.tipo,
            "conteudos": request.conteudos,
            "titulo": request.titulo,
            "data_avaliacao": request.data_avaliacao,
            "serie": request.serie
        }
        tipo_usuario = getattr(request, "tipo_usuario", None) or "usuario"
        responsavel = getattr(request, "professor", None)
        historico_service.add_record(tipo_usuario, nome_arquivo, meta, responsavel)
    except Exception:
        logger.exception("Erro ao salvar histórico da prévia")

    return FileResponse(
        arquivo,
        media_type="application/pdf",
        filename=nome_arquivo
    )


@router.post("/previsualizar-atividade")
def previsualizar_atividade(request: AtividadeRequest):
    try:
        return service.previsualizar(
            disciplina_id=request.disciplina_id,
            quantidade=request.quantidade,
            dificuldade=request.dificuldade,
            tipo=request.tipo,
            conteudo=request.conteudos,
            titulo=request.titulo,
            incluir_gabarito=request.incluir_gabarito,
            professor=request.professor,
            data_avaliacao=request.data_avaliacao,
            serie=request.serie,
            tipo_usuario=request.tipo_usuario
        )
    except Exception as e:
        logger.exception("Erro ao criar prévia da atividade")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/previsualizar-atividade/trocar")
def trocar_questao_previa(request: PreviewActionRequest):
    try:
        return service.trocar_questao_previa(
            preview_id=request.preview_id,
            questao_id=request.questao_id
        )
    except ValueError as e:
        logger.warning("Erro ao trocar questão da prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/previsualizar-atividade/remover")
def remover_questao_previa(request: PreviewActionRequest):
    try:
        return service.remover_questao_previa(
            preview_id=request.preview_id,
            questao_id=request.questao_id
        )
    except ValueError as e:
        logger.warning("Erro ao remover questão da prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gerar-atividade-preview")
def gerar_atividade_preview(request: PreviewGenerateRequest):
    try:
        resultado = service.gerar_previa(request.preview_id)
    except ValueError as e:
        logger.warning("Erro ao gerar PDF da prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))

    arquivo = resultado.get("arquivo")
    if not arquivo:
        raise HTTPException(status_code=500, detail="Erro ao gerar arquivo")

    try:
        nome_arquivo = Path(arquivo).name
        meta = resultado.get("meta", {})
        tipo_usuario = meta.get("tipo_usuario") or "usuario"
        responsavel = meta.get("professor")
        historico_service.add_record(tipo_usuario, nome_arquivo, meta, responsavel)
    except Exception:
        logger.exception("Erro ao salvar histórico da atividade")

    return FileResponse(
        arquivo,
        media_type="application/pdf",
        filename=Path(arquivo).name
    )


@router.get("/historico/tipo/{tipo}")
def listar_historico_tipo(tipo: str):
    return historico_service.list(tipo=tipo)


@router.get("/historico/professor/{nome}")
def listar_historico_professor(nome: str):
    return historico_service.list(responsavel=nome)


@router.get("/usuario")
def get_usuario():
    return user_service.get_profile()


@router.post("/usuario")
def set_usuario(profile: UserProfile):
    user_service.set_profile(profile.dict())
    return {"ok": True}


@router.get("/historico/download/{filename}")
def download_historico(filename: str):
    base = Path("generated/pdfs").resolve()
    target = (base / filename).resolve()
    if not str(target).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Arquivo inválido")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    return FileResponse(str(target), media_type="application/pdf", filename=filename)
