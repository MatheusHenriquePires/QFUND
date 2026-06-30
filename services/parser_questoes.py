# services/parser_questoes.py

import re
from bs4 import BeautifulSoup


class QuestaoParser:

    ALTERNATIVA_REGEX = re.compile(
        r"^[A-E]\)",
        re.IGNORECASE
    )
    CREDITO_IMAGEM_REGEX = re.compile(
        r"Dispon.vel\s+em\s*:\s*.*?Acesso\s+em\s*:\s*\d{1,2}\s+[^\s.]+\.?\s+\d{4}\.?",
        re.IGNORECASE | re.DOTALL
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

    def separar_creditos_imagem(self, texto):
        creditos = [
            self._normalizar_espacos(match.group(0))
            for match in self.CREDITO_IMAGEM_REGEX.finditer(texto or "")
        ]

        texto_sem_creditos = self.CREDITO_IMAGEM_REGEX.sub("", texto or "")
        texto_sem_creditos = re.sub(r"\n{2,}", "\n", texto_sem_creditos)

        return texto_sem_creditos.strip(), creditos

    def _normalizar_espacos(self, texto):
        return re.sub(r"\s+", " ", str(texto or "")).strip()

    def detectar_tipo(self, alternativas, tipo_api=None):

        tipo_normalizado = str(tipo_api or "").strip().lower()
        if tipo_normalizado == "objetiva":
            return "objetiva"
        if tipo_normalizado == "discursiva":
            return "discursiva"

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
        texto, creditos_imagem = self.separar_creditos_imagem(texto)

        alternativas = self.extrair_alternativas(
            texto
        )

        tipo = self.detectar_tipo(
            alternativas,
            questao.get("questionType"),
        )

        dificuldade = self._normalizar_dificuldade(questao.get("difficulty"))

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

            "dificuldade": dificuldade,

            "origem": questao.get(
                "source"
            ),

            "conteudo": questao.get(
                "breadcrumbs"
            ),

            "area": questao.get(
                "knowledgeArea"
            ),

            "habilidade": questao.get("skill"),

            "tipo_api": questao.get("questionType"),

            "resposta_esperada": self.limpar_html(questao.get("answer", "")),

            "keywords": questao.get(
                "keywords"
            ),

            "tags": questao.get("tags") or [],

            "raw": questao,

            "imagens": imagens,
            "creditos_imagem": creditos_imagem
        }

    def _normalizar_dificuldade(self, dificuldade):
        mapa = {
            "facil": "Fácil", "fácil": "Fácil",
            "medio": "Médio", "médio": "Médio",
            "dificil": "Difícil", "difícil": "Difícil",
        }
        valor = str(dificuldade or "").strip()
        return mapa.get(valor.lower(), valor or "Não informada")
