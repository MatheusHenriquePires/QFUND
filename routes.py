import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pathlib import Path

from services.atividade_service import AtividadeService
from schemas import (
    AtividadeRequest,
    PreviewActionRequest,
    PreviewGenerateRequest,
    PreviewQuestionEditRequest,
    PreviewQuestionCreateRequest,
    UserProfile,
    RegisterRequest,
    LoginRequest,
    QuestionSyncRequest,
)
from database import db
from services.auth_service import auth_service
from services.conteudos_service import ConteudosService
from services.historico_service import HistoricoService
from services.user_service import UserService
from services.question_sync_service import question_sync_service
from services.question_persistence_service import question_persistence_service


SESSION_COOKIE = "qfund_session"


def require_current_user(request: Request):
    authorization = request.headers.get("Authorization", "")
    bearer_token = authorization[7:].strip() if authorization.lower().startswith("bearer ") else None
    token = bearer_token or request.cookies.get(SESSION_COOKIE)
    user = auth_service.user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Faça login para continuar")
    return user


conteudos_service = ConteudosService()
auth_router = APIRouter(prefix="/auth")
router = APIRouter(dependencies=[Depends(require_current_user)])
logger = logging.getLogger("qfund.routes")

service = AtividadeService()
historico_service = HistoricoService()
user_service = UserService()


def _auth_response(user, token, request: Request, status_code=200):
    response = JSONResponse(
        {"ok": True, "usuario": auth_service.public_user(user)}, status_code=status_code
    )
    response.set_cookie(
        SESSION_COOKIE, token, max_age=auth_service.TOKEN_TTL_SECONDS, httponly=True,
        secure=request.url.scheme == "https", samesite="strict", path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@auth_router.post("/cadastro")
def cadastrar(data: RegisterRequest, request: Request):
    try:
        user, token = auth_service.register(data.email, data.senha, data.nome, data.tipo)
        return _auth_response(user, token, request, status_code=201)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@auth_router.post("/login")
def login(data: LoginRequest, request: Request):
    try:
        user, token = auth_service.login(data.email, data.senha)
        return _auth_response(user, token, request)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@auth_router.post("/logout")
def logout(request: Request):
    auth_service.revoke_token(request.cookies.get(SESSION_COOKIE))
    response = JSONResponse({"ok": True})
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/auth/me")
def current_user(user=Depends(require_current_user)):
    return auth_service.public_user(user)


@router.post("/banco/sincronizar", status_code=202)
def start_question_sync(data: QuestionSyncRequest, user=Depends(require_current_user)):
    if user.get("role") != "professor":
        raise HTTPException(status_code=403, detail="Apenas professores podem sincronizar o banco")
    try:
        run_id = question_sync_service.start_background(
            download_images=data.baixar_imagens,
            classify_grades=data.classificar_series,
        )
        return {"ok": True, "run_id": run_id, "status": "running"}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/banco/status")
def question_bank_status():
    return {
        "sincronizacao": db.latest_sync_run(),
        "estatisticas": db.bank_statistics(),
        "gravacao_segundo_plano": question_persistence_service.status(),
    }

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


@router.get("/conteudos/{disciplina_id}/contagens")
def contar_questoes_por_conteudo(
    disciplina_id: str,
    serie: str | None = None,
    dificuldade: str | None = None,
    tipo: str | None = None
):
    try:
        return conteudos_service.contar_questoes_por_conteudo(
            disciplina_id=disciplina_id,
            serie=serie,
            dificuldade=dificuldade,
            tipo=tipo,
        )
    except Exception as e:
        logger.exception("Erro ao contar questões por conteúdo")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conteudos/{disciplina_id}")
def listar_conteudos(disciplina_id: str):
    return service.conteudos(disciplina_id)


@router.post("/gerar-atividade")
def gerar_atividade(request: AtividadeRequest, user=Depends(require_current_user)):
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
        historico_service.add_record(user["id"], tipo_usuario, nome_arquivo, meta, responsavel)
    except Exception:
        logger.exception("Erro ao salvar histórico da prévia")

    return FileResponse(
        arquivo,
        media_type="application/pdf",
        filename=nome_arquivo
    )


@router.post("/previsualizar-atividade")
def previsualizar_atividade(request: AtividadeRequest, user=Depends(require_current_user)):
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
            tipo_usuario=request.tipo_usuario,
            user_id=user["id"],
        )
    except Exception as e:
        logger.exception("Erro ao criar prévia da atividade")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/previsualizar-atividade/trocar")
def trocar_questao_previa(request: PreviewActionRequest, user=Depends(require_current_user)):
    try:
        return service.trocar_questao_previa(
            preview_id=request.preview_id,
            questao_id=request.questao_id,
            tipo=request.tipo,
            user_id=user["id"],
        )
    except ValueError as e:
        logger.warning("Erro ao trocar questão da prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/previsualizar-atividade/remover")
def remover_questao_previa(request: PreviewActionRequest, user=Depends(require_current_user)):
    try:
        return service.remover_questao_previa(
            preview_id=request.preview_id,
            questao_id=request.questao_id,
            user_id=user["id"],
        )
    except ValueError as e:
        logger.warning("Erro ao remover questão da prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/previsualizar-atividade/adicionar")
def adicionar_questao_previa(request: PreviewQuestionCreateRequest, user=Depends(require_current_user)):
    try:
        return service.adicionar_questao_manual_previa(
            preview_id=request.preview_id,
            questao_id=request.questao_id,
            tipo=request.tipo,
            enunciado=request.enunciado,
            alternativas=request.alternativas,
            gabarito=request.gabarito,
            conteudo=request.conteudo,
            dificuldade=request.dificuldade,
            user_id=user["id"],
        )
    except ValueError as e:
        logger.warning("Erro ao adicionar questão manual na prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/previsualizar-atividade/editar")
def editar_questao_previa(request: PreviewQuestionEditRequest, user=Depends(require_current_user)):
    try:
        return service.editar_questao_previa(
            preview_id=request.preview_id,
            questao_id=request.questao_id,
            enunciado=request.enunciado,
            linhas_resposta=request.linhas_resposta,
            user_id=user["id"],
        )
    except ValueError as e:
        logger.warning("Erro ao editar questão da prévia: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/gerar-atividade-preview")
def gerar_atividade_preview(request: PreviewGenerateRequest, user=Depends(require_current_user)):
    try:
        resultado = service.gerar_previa(request.preview_id, user["id"])
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
        historico_service.add_record(user["id"], tipo_usuario, nome_arquivo, meta, responsavel)
    except Exception:
        logger.exception("Erro ao salvar histórico da atividade")

    return FileResponse(
        arquivo,
        media_type="application/pdf",
        filename=Path(arquivo).name
    )


@router.get("/historico/tipo/{tipo}")
def listar_historico_tipo(tipo: str, user=Depends(require_current_user)):
    return historico_service.list(user["id"], tipo=tipo)


@router.get("/historico/professor/{nome}")
def listar_historico_professor(nome: str, user=Depends(require_current_user)):
    return historico_service.list(user["id"], responsavel=nome)


@router.get("/usuario")
def get_usuario(user=Depends(require_current_user)):
    return user_service.get_profile(user["id"])


@router.post("/usuario")
def set_usuario(profile: UserProfile, user=Depends(require_current_user)):
    data = profile.model_dump() if hasattr(profile, "model_dump") else profile.dict()
    user_service.set_profile(user["id"], data)
    return {"ok": True}


@router.get("/questoes/imagens/{image_id}")
def get_question_image(image_id: int):
    stored = db.get_image(image_id)
    if not stored:
        raise HTTPException(status_code=404, detail="Imagem não encontrada")
    content, media_type = stored
    return Response(content=content, media_type=media_type,
                    headers={"Cache-Control": "private, max-age=86400"})


@router.get("/historico/download/{filename}")
def download_historico(filename: str, user=Depends(require_current_user)):
    base = Path("generated/pdfs").resolve()
    target = (base / filename).resolve()
    if not target.is_relative_to(base):
        raise HTTPException(status_code=400, detail="Arquivo inválido")
    if not target.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")
    if not historico_service.owns_file(user["id"], filename):
        raise HTTPException(status_code=403, detail="Arquivo não pertence a este usuário")
    return FileResponse(str(target), media_type="application/pdf", filename=filename)
