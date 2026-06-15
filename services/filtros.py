import random


class QuestaoFiltro:

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
                str(c).lower()
                for c in conteudo
            ]

            resultado = [
                q
                for q in resultado
                if any(
                    c in str(
                        q.get("conteudo", "")
                    ).lower()
                    for c in conteudo
                )
            ]

        # dificuldade
        if dificuldade and dificuldade != "string":

            resultado = [
                q
                for q in resultado
                if str(
                    q.get("dificuldade", "")
                ).lower()
                ==
                str(dificuldade).lower()
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