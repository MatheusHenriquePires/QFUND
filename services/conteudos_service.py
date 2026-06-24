from services.bernoulli import BernoulliClient
import re
import unicodedata


class ConteudosService:
    PER_PAGE_QUESTOES = 100
    MAX_PAGINAS_CONTAGEM = 30

    def __init__(self):
        self.client = BernoulliClient()

    def listar(self, disciplina_id: str):

        resposta = self.client.conteudos(
            disciplina_id
        )

        return resposta.get("data", [])

    def listar_formatado(self, disciplina_id: str):

        conteudos = self.listar(
            disciplina_id
        )

        resultado = []

        for item in conteudos:

            resultado.append({
                "id": item.get("id"),
                "nome": item.get("name"),
                "subitens": item.get(
                    "subitens",
                    []
                )
            })

        return resultado

    def buscar_conteudo(
        self,
        disciplina_id: str,
        conteudo_id: str
    ):

        conteudos = self.listar(
            disciplina_id
        )

        for item in conteudos:

            if str(item.get("id")) == str(conteudo_id):
                return item

            for subitem in item.get(
                "subitens",
                []
            ):

                if str(
                    subitem.get("id")
                ) == str(conteudo_id):

                    return subitem

        return None

    def contar_questoes_por_conteudo(
        self,
        disciplina_id: str,
        serie: str | None = None,
        dificuldade: str | None = None,
        tipo: str | None = None
    ):
        conteudos = self.client.conteudos(disciplina_id)
        indice = self._indexar_conteudos(conteudos)
        contagens = {
            item["id"]: 0
            for item in indice
        }

        pagina = 1
        total_lidas = 0
        completo = True

        while pagina <= self.MAX_PAGINAS_CONTAGEM:
            resposta = self.client.questoes(
                disciplina=disciplina_id,
                page=pagina,
                per_page=self.PER_PAGE_QUESTOES,
                serie=serie,
                dificuldade=dificuldade,
                tipo=tipo,
            )

            questoes = resposta.get("data", [])
            if not questoes:
                break

            total_lidas += len(questoes)

            for questao in questoes:
                breadcrumb = self._normalizar_texto(
                    questao.get("breadcrumbs", "")
                )

                if not breadcrumb:
                    continue

                for item in indice:
                    if self._conteudo_bate_breadcrumb(item, breadcrumb):
                        contagens[item["id"]] += 1

            if len(questoes) < self.PER_PAGE_QUESTOES:
                break

            pagina += 1
        else:
            completo = False

        return {
            "disciplina_id": disciplina_id,
            "serie": serie,
            "total_questoes_lidas": total_lidas,
            "completo": completo,
            "contagens": contagens,
        }

    def _indexar_conteudos(self, conteudos):
        indice = []

        def visitar(itens, caminho=None):
            caminho = caminho or []

            for item in itens or []:
                item_id = item.get("id")
                nome = item.get("name") or item.get("nome")
                caminho_atual = [*caminho, nome] if nome else caminho

                if item_id and nome:
                    indice.append({
                        "id": str(item_id),
                        "nome": self._normalizar_texto(nome),
                        "caminho": self._normalizar_texto(
                            " > ".join(caminho_atual)
                        ),
                    })

                visitar(item.get("subitens", []), caminho_atual)

        visitar(conteudos)
        return indice

    def _conteudo_bate_breadcrumb(self, item, breadcrumb):
        caminho = item.get("caminho")
        nome = item.get("nome")

        return (
            bool(caminho and caminho in breadcrumb)
            or bool(nome and nome in breadcrumb)
        )

    def _normalizar_texto(self, valor):
        texto = str(valor or "").lower()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(
            c
            for c in texto
            if not unicodedata.combining(c)
        )
        texto = re.sub(r"[^a-z0-9]+", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        return texto.strip()
