from services.bernoulli import BernoulliClient
from services.parser_questoes import QuestaoParser
from services.filtros import QuestaoFiltro
from services.pdf_generator import PDFGenerator
import re
import uuid


class AtividadeService:

    PER_PAGE_QUESTOES = 100
    MAX_PAGINAS_QUESTOES = 30

    def __init__(self):
        self.client = BernoulliClient()
        self.parser = QuestaoParser()
        self.filtro = QuestaoFiltro()
        self.pdf = PDFGenerator()
        self.previews = {}

    def disciplinas(self):
        return self.client.disciplinas()

    def conteudos(self, disciplina):
        return self.client.conteudos(disciplina)

    def gerar(
        self,
        disciplina_id,
        quantidade=10,
        dificuldade=None,
        tipo=None,
        conteudo=None,
        titulo="Atividade",
        incluir_gabarito=False,
        professor=None,
        data_avaliacao=None,
        serie=None,
        tipo_usuario=None
    ):

        if conteudo == []:
            conteudo = None

        conteudo_filtro = self._resolver_conteudos_para_filtro(
            disciplina_id,
            conteudo
        )

        questoes = self._buscar_questoes_filtradas(
            disciplina_id=disciplina_id,
            quantidade=quantidade,
            conteudo=conteudo_filtro,
            dificuldade=dificuldade,
            tipo=tipo,
            serie=serie,
        )

        questoes = self.filtro.selecionar(
            questoes,
            quantidade=quantidade
        )

        disciplina_nome = self._nome_disciplina(disciplina_id)

        arquivo = self.pdf.gerar_atividade(
            questoes=questoes,
            disciplina=disciplina_nome,
            titulo=titulo,
            conteudo=conteudo,
            incluir_gabarito=incluir_gabarito,
            professor=professor,
            data_avaliacao=data_avaliacao,
            serie=serie
        )

        return {
            "success": True,
            "quantidade": len(questoes),
            "arquivo": arquivo
        }

    def previsualizar(
        self,
        disciplina_id,
        quantidade=10,
        dificuldade=None,
        tipo=None,
        conteudo=None,
        titulo="Atividade",
        incluir_gabarito=False,
        professor=None,
        data_avaliacao=None,
        serie=None,
        tipo_usuario=None
    ):
        if conteudo == []:
            conteudo = None

        conteudo_filtro = self._resolver_conteudos_para_filtro(
            disciplina_id,
            conteudo
        )

        alvo_busca = max(int(quantidade or 10) * 3, int(quantidade or 10))
        candidatas = self._buscar_questoes_filtradas(
            disciplina_id=disciplina_id,
            quantidade=alvo_busca,
            conteudo=conteudo_filtro,
            dificuldade=dificuldade,
            tipo=tipo,
            serie=serie,
        )

        candidatas = self.filtro.selecionar(
            candidatas,
            quantidade=len(candidatas)
        )

        quantidade_solicitada = int(quantidade or 10)
        selecionadas = candidatas[:quantidade_solicitada]
        reserva = candidatas[quantidade_solicitada:]
        preview_id = str(uuid.uuid4())
        disciplina_nome = self._nome_disciplina(disciplina_id)

        self.previews[preview_id] = {
            "disciplina_id": disciplina_id,
            "disciplina": disciplina_nome,
            "questoes": selecionadas,
            "reserva": reserva,
            "meta": {
                "disciplina_id": disciplina_id,
                "quantidade": quantidade_solicitada,
                "dificuldade": dificuldade,
                "tipo": tipo,
                "conteudo": conteudo,
                "titulo": titulo,
                "incluir_gabarito": incluir_gabarito,
                "professor": professor,
                "data_avaliacao": data_avaliacao,
                "serie": serie,
                "tipo_usuario": tipo_usuario,
            }
        }

        return self._preview_payload(preview_id)

    def trocar_questao_previa(self, preview_id, questao_id, tipo=None):
        preview = self._obter_previa(preview_id)
        questoes = preview["questoes"]
        reserva = preview["reserva"]

        indice = next(
            (
                i
                for i, questao in enumerate(questoes)
                if str(questao.get("id")) == str(questao_id)
            ),
            None
        )

        if indice is None:
            raise ValueError("Questão não encontrada na prévia")

        tipo = (tipo or "").strip().lower() or None
        if tipo and tipo not in ("objetiva", "discursiva"):
            raise ValueError("Tipo de questão inválido")

        reserva_indice = self._indice_reserva_por_tipo(reserva, tipo)
        substituta = None

        if reserva_indice is not None:
            substituta = reserva.pop(reserva_indice)
        elif tipo:
            substituta = self._buscar_substituta_previa(preview, tipo)

        if not substituta:
            if tipo:
                raise ValueError(
                    f"Não há questão {tipo} disponível para troca com esses filtros"
                )
            raise ValueError("Não há questões reservas para troca")

        reserva.append(questoes[indice])
        questoes[indice] = substituta

        return self._preview_payload(preview_id)

    def _indice_reserva_por_tipo(self, reserva, tipo=None):
        if not reserva:
            return None

        if not tipo:
            return 0

        for indice, questao in enumerate(reserva):
            if (questao.get("tipo") or "").strip().lower() == tipo:
                return indice

        return None

    def _buscar_substituta_previa(self, preview, tipo):
        meta = preview["meta"]
        conteudo_filtro = self._resolver_conteudos_para_filtro(
            preview["disciplina_id"],
            meta.get("conteudo")
        )

        ids_usados = {
            str(questao.get("id"))
            for questao in [*preview["questoes"], *preview["reserva"]]
            if questao.get("id") is not None
        }

        candidatas = self._buscar_questoes_filtradas(
            disciplina_id=preview["disciplina_id"],
            quantidade=self.PER_PAGE_QUESTOES,
            conteudo=conteudo_filtro,
            dificuldade=meta.get("dificuldade"),
            tipo=tipo,
            serie=meta.get("serie"),
        )

        candidatas = self.filtro.selecionar(
            [
                questao
                for questao in candidatas
                if str(questao.get("id")) not in ids_usados
            ],
            quantidade=len(candidatas)
        )

        return candidatas[0] if candidatas else None

    def remover_questao_previa(self, preview_id, questao_id):
        preview = self._obter_previa(preview_id)
        questoes = preview["questoes"]

        preview["questoes"] = [
            questao
            for questao in questoes
            if str(questao.get("id")) != str(questao_id)
        ]

        return self._preview_payload(preview_id)

    def adicionar_questao_manual_previa(
        self,
        preview_id,
        tipo,
        enunciado,
        alternativas=None,
        gabarito=None,
        conteudo=None,
        dificuldade=None,
    ):
        preview = self._obter_previa(preview_id)
        quantidade_solicitada = int(preview["meta"].get("quantidade") or 0)

        if quantidade_solicitada and len(preview["questoes"]) >= quantidade_solicitada:
            raise ValueError("A prévia já tem a quantidade solicitada de questões")

        tipo = (tipo or "").strip().lower()
        if tipo not in ("objetiva", "discursiva"):
            raise ValueError("Escolha se a questão é objetiva ou discursiva")

        enunciado = self._limpar_texto_manual(enunciado, limite=5000)
        if not enunciado:
            raise ValueError("Informe o enunciado da questão")

        alternativas_formatadas = []
        gabarito_formatado = None

        if tipo == "objetiva":
            alternativas_formatadas = self._formatar_alternativas_manuais(
                alternativas or []
            )
            if len(alternativas_formatadas) < 2:
                raise ValueError("Informe pelo menos duas alternativas")

            letras_validas = "ABCDE"[:len(alternativas_formatadas)]
            gabarito_formatado = (gabarito or "").strip().upper()
            if gabarito_formatado not in letras_validas:
                raise ValueError(
                    f"Escolha um gabarito entre {', '.join(letras_validas)}"
                )

        questao = {
            "id": f"manual:{uuid.uuid4()}",
            "tipo": tipo,
            "enunciado": enunciado,
            "alternativas": alternativas_formatadas,
            "gabarito": gabarito_formatado,
            "imagens": [],
            "conteudo": self._limpar_texto_manual(conteudo, limite=200) or "Criada pelo professor",
            "dificuldade": self._limpar_texto_manual(dificuldade, limite=50) or "Manual",
            "origem": "manual",
        }

        preview["questoes"].append(questao)
        return self._preview_payload(preview_id)

    def _limpar_texto_manual(self, texto, limite):
        texto = str(texto or "").replace("\x00", "").strip()
        texto = re.sub(r"\s+\n", "\n", texto)
        texto = re.sub(r"\n{3,}", "\n\n", texto)
        texto = re.sub(r"[ \t]{2,}", " ", texto)

        return texto[:limite].strip()

    def _formatar_alternativas_manuais(self, alternativas):
        letras = "ABCDE"
        textos = [
            self._limpar_texto_manual(alternativa, limite=1000)
            for alternativa in alternativas
        ]
        textos = [texto for texto in textos if texto][:5]

        return [
            f"{letras[indice]}) {texto}"
            for indice, texto in enumerate(textos)
        ]

    def gerar_previa(self, preview_id):
        preview = self._obter_previa(preview_id)
        meta = preview["meta"]

        if not preview["questoes"]:
            raise ValueError(
                "Não há questões na prévia para gerar o PDF. "
                "Ajuste os filtros e tente novamente."
            )

        arquivo = self.pdf.gerar_atividade(
            questoes=preview["questoes"],
            disciplina=preview["disciplina"],
            titulo=meta.get("titulo") or "Atividade",
            conteudo=meta.get("conteudo"),
            incluir_gabarito=bool(meta.get("incluir_gabarito")),
            professor=meta.get("professor"),
            data_avaliacao=meta.get("data_avaliacao"),
            serie=meta.get("serie"),
        )

        return {
            "success": True,
            "quantidade": len(preview["questoes"]),
            "arquivo": arquivo,
            "meta": meta,
        }

    def _obter_previa(self, preview_id):
        preview = self.previews.get(preview_id)
        if not preview:
            raise ValueError("Prévia não encontrada ou expirada")

        return preview

    def _preview_payload(self, preview_id):
        preview = self._obter_previa(preview_id)
        questoes = preview["questoes"]

        return {
            "preview_id": preview_id,
            "disciplina": preview["disciplina"],
            "quantidade": len(questoes),
            "quantidade_solicitada": int(preview["meta"].get("quantidade") or len(questoes)),
            "reservas": len(preview["reserva"]),
            "meta": preview["meta"],
            "avisos": self._avisos_previa(preview),
            "estatisticas": self._estatisticas_questoes(questoes),
            "questoes": [
                self._questao_preview(questao, index + 1)
                for index, questao in enumerate(questoes)
            ],
        }

    def _avisos_previa(self, preview):
        avisos = []
        quantidade_solicitada = int(
            preview.get("meta", {}).get("quantidade") or 0
        )
        quantidade_encontrada = len(preview.get("questoes", []))

        if quantidade_solicitada and quantidade_encontrada < quantidade_solicitada:
            avisos.append({
                "tipo": "quantidade_insuficiente",
                "mensagem": (
                    f"Foram encontradas apenas {quantidade_encontrada} "
                    f"questões para os filtros escolhidos, de "
                    f"{quantidade_solicitada} solicitadas."
                )
            })

        return avisos

    def _questao_preview(self, questao, numero):
        return {
            "numero": numero,
            "id": questao.get("id"),
            "tipo": questao.get("tipo"),
            "enunciado": questao.get("enunciado", ""),
            "alternativas": questao.get("alternativas", []),
            "imagens": questao.get("imagens", []),
            "gabarito": questao.get("gabarito"),
            "conteudo": questao.get("conteudo"),
            "dificuldade": questao.get("dificuldade"),
            "origem": questao.get("origem"),
        }

    def _estatisticas_questoes(self, questoes):
        stats = {
            "objetivas": 0,
            "discursivas": 0,
            "com_imagem": 0,
            "dificuldades": {}
        }

        for questao in questoes:
            tipo = questao.get("tipo")
            if tipo == "objetiva":
                stats["objetivas"] += 1
            elif tipo == "discursiva":
                stats["discursivas"] += 1

            if questao.get("imagens"):
                stats["com_imagem"] += 1

            dificuldade = questao.get("dificuldade") or "Sem dificuldade"
            stats["dificuldades"][dificuldade] = (
                stats["dificuldades"].get(dificuldade, 0) + 1
            )

        return stats

    def _resolver_conteudos_para_filtro(self, disciplina_id, conteudo):
        if not conteudo:
            return None

        if not isinstance(conteudo, list):
            conteudo = [conteudo]

        indice = self._indexar_conteudos(disciplina_id)
        termos = []

        for item in conteudo:
            chave = self._normalizar_id_conteudo(item)
            dados = indice.get(chave)

            if dados:
                termos.extend(dados)
                continue

            termos.append(str(item))

        termos_unicos = []
        vistos = set()

        for termo in termos:
            termo = str(termo or "").strip()
            if not termo:
                continue

            for parte in self._expandir_termo_conteudo(termo):
                chave = parte.lower()
                if chave not in vistos:
                    vistos.add(chave)
                    termos_unicos.append(parte)

        return termos_unicos or None

    def _indexar_conteudos(self, disciplina_id):
        indice = {}
        conteudos = self.client.conteudos(disciplina_id)

        def visitar(itens, ancestrais=None):
            ancestrais = ancestrais or []

            for item in itens or []:
                item_id = item.get("id")
                nome = item.get("name")
                termos = [*ancestrais, nome] if nome else ancestrais
                descendentes = []

                def coletar_descendentes(filhos):
                    for filho in filhos or []:
                        filho_nome = filho.get("name")
                        if filho_nome:
                            descendentes.append(filho_nome)
                        coletar_descendentes(filho.get("subitens", []))

                coletar_descendentes(item.get("subitens", []))

                if item_id and nome:
                    chave = self._normalizar_id_conteudo(item_id)
                    indice[chave] = [*termos, *descendentes]

                visitar(item.get("subitens", []), termos)

        visitar(conteudos)
        return indice

    def _normalizar_id_conteudo(self, valor):
        return re.sub(r"[^0-9a-zA-Z]", "", str(valor or ""))

    def _expandir_termo_conteudo(self, termo):
        partes = [termo]

        if ":" in termo:
            partes.append(termo.split(":", 1)[1])

        for separador in (" > ", " e ", ","):
            novas_partes = []
            for parte in partes:
                novas_partes.append(parte)
                novas_partes.extend(parte.split(separador))
            partes = novas_partes

        return [
            parte.strip()
            for parte in partes
            if parte and len(parte.strip()) > 2
        ]

    def _nome_disciplina(self, disciplina_id):
        try:
            disciplinas = self.client.disciplinas().get("data", [])
            for disciplina in disciplinas:
                if str(disciplina.get("id")) == str(disciplina_id):
                    return disciplina.get("name") or str(disciplina_id)
        except Exception:
            pass

        return str(disciplina_id)

    def _buscar_questoes_filtradas(
        self,
        disciplina_id,
        quantidade,
        conteudo=None,
        dificuldade=None,
        tipo=None,
        serie=None
    ):
        questoes = []
        pagina = 1

        while pagina <= self.MAX_PAGINAS_QUESTOES and len(questoes) < quantidade:
            resposta = self.client.questoes(
                disciplina=disciplina_id,
                page=pagina,
                per_page=self.PER_PAGE_QUESTOES,
                fetch_all=False,
                dificuldade=dificuldade,
                tipo=tipo,
                serie=serie
            )

            questoes_brutas = resposta.get("data", [])
            if not questoes_brutas:
                break

            lote = [
                self.parser.parse(q)
                for q in questoes_brutas
            ]

            lote = self.filtro.filtrar(
                lote,
                conteudo=conteudo,
                dificuldade=dificuldade,
                tipo=tipo
            )

            questoes.extend(lote)
            pagina += 1

        return questoes
