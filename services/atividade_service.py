from services.bernoulli import BernoulliClient
from services.parser_questoes import QuestaoParser
from services.filtros import QuestaoFiltro
from services.pdf_generator import PDFGenerator
import re


class AtividadeService:

    PER_PAGE_QUESTOES = 50
    MAX_PAGINAS_QUESTOES = 12

    def __init__(self):
        self.client = BernoulliClient()
        self.parser = QuestaoParser()
        self.filtro = QuestaoFiltro()
        self.pdf = PDFGenerator()

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
        data_avaliacao=None
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
            data_avaliacao=data_avaliacao
        )

        return {
            "success": True,
            "quantidade": len(questoes),
            "arquivo": arquivo
        }

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

        for separador in (" e ", ","):
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
        tipo=None
    ):
        questoes = []
        pagina = 1

        while pagina <= self.MAX_PAGINAS_QUESTOES and len(questoes) < quantidade:
            resposta = self.client.questoes(
                disciplina=disciplina_id,
                page=pagina,
                per_page=self.PER_PAGE_QUESTOES,
                fetch_all=False
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
