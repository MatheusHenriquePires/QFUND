# services/parser_questoes.py

import re
from bs4 import BeautifulSoup


class QuestaoParser:

    ALTERNATIVA_REGEX = re.compile(
        r"^[A-E]\)",
        re.IGNORECASE
    )

    def limpar_html(self, html):

        if not html:
            return ""

        texto = BeautifulSoup(
            html,
            "html.parser"
        ).get_text("\n")

        texto = texto.replace("\xa0", " ")

        texto = re.sub(r"\n+", "\n", texto)

        return texto.strip()

    def separar_linhas(self, texto):

        return [
            linha.strip()
            for linha in texto.split("\n")
            if linha.strip()
        ]

    def extrair_alternativas(self, texto):

        linhas = self.separar_linhas(texto)

        alternativas = []
        atual = None

        for linha in linhas:

            if self.ALTERNATIVA_REGEX.match(linha):

                if atual:
                    alternativas.append(atual)

                atual = linha

            elif atual:

                atual += " " + linha

        if atual:
            alternativas.append(atual)

        return alternativas

    def extrair_enunciado(self, texto):

        linhas = self.separar_linhas(texto)

        enunciado = []

        for linha in linhas:

            if self.ALTERNATIVA_REGEX.match(linha):
                break

            enunciado.append(linha)

        return "\n".join(enunciado)

    def detectar_tipo(self, alternativas):

        if len(alternativas) >= 2:
            return "objetiva"

        return "discursiva"

    def parse(self, questao):

        html = questao.get("statement", "")

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        imagens = []

        for img in soup.find_all("img"):

            src = img.get("src")

            if src:
                imagens.append(src)

        texto = self.limpar_html(html)

        alternativas = self.extrair_alternativas(
            texto
        )

        tipo = self.detectar_tipo(
            alternativas
        )

        return {
            "id": questao.get("id"),

            "tipo": tipo,

            "enunciado": self.extrair_enunciado(
                texto
            ),

            "alternativas": alternativas,

            "gabarito": questao.get(
                "correctAnswer"
            ),

            "resolucao": self.limpar_html(
                questao.get(
                    "resolution",
                    ""
                )
            ),

            "ano": questao.get(
                "year"
            ),

            "dificuldade": questao.get(
                "difficulty"
            ),

            "origem": questao.get(
                "source"
            ),

            "conteudo": questao.get(
                "breadcrumbs"
            ),

            "area": questao.get(
                "knowledgeArea"
            ),

            "keywords": questao.get(
                "keywords"
            ),

            "imagens": imagens
        }