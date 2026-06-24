import random
import re
import unicodedata


class QuestaoFiltro:

    def normalizar_texto(self, valor):
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

    def filtrar(
        self,
        questoes,
        conteudo=None,
        dificuldade=None,
        ano=None,
        tipo=None
    ):

        resultado = questoes

        # Conteúdo
        if conteudo:

            if not isinstance(conteudo, list):
                conteudo = [conteudo]

            conteudo = [
                self.normalizar_texto(c)
                for c in conteudo
                if self.normalizar_texto(c)
            ]

            resultado = [
                q
                for q in resultado
                if any(
                    c in self.normalizar_texto(q.get("conteudo", ""))
                    for c in conteudo
                )
            ]

        # dificuldade
        if dificuldade and dificuldade != "string":
            dificuldade_normalizada = self.normalizar_texto(dificuldade)

            resultado = [
                q
                for q in resultado
                if self.normalizar_texto(q.get("dificuldade", ""))
                ==
                dificuldade_normalizada
            ]

        # ano
        if ano:

            resultado = [
                q
                for q in resultado
                if str(q.get("ano")) == str(ano)
            ]

        # tipo
        if tipo and tipo != "string":

            resultado = [
                q
                for q in resultado
                if str(
                    q.get("tipo", "")
                ).lower()
                ==
                str(tipo).lower()
            ]

        return resultado

    def selecionar(
        self,
        questoes,
        quantidade=10,
        embaralhar=True
    ):

        questoes = list(questoes)

        if embaralhar:
            random.shuffle(questoes)

        return questoes[:quantidade]
