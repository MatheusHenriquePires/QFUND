from services.bernoulli import BernoulliClient
from services.parser_questoes import QuestaoParser
from services.filtros import QuestaoFiltro
from services.pdf_generator import PDFGenerator


class AtividadeService:

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
        titulo="Atividade"
    ):

        resposta = self.client.questoes(
            disciplina=disciplina_id,
            per_page=100
        )

        questoes_brutas = resposta["data"]

        print("\n===== CHAVES DA QUESTÃO =====")
        print(questoes_brutas[0].keys())

        for q in questoes_brutas:
            if "<img" in q.get("statement", "").lower():

                print("\n=== QUESTÃO COM IMG ===")
                print(q["statement"])

                print("\n=== CHAVES ===")
                print(q.keys())

                break

        print("\n===== TOTAL BRUTO =====")
        print(len(questoes_brutas))

        questoes = [
            self.parser.parse(q)
            for q in questoes_brutas
        ]

        print("\n===== TOTAL PARSEADO =====")
        print(len(questoes))

        if conteudo == []:
            conteudo = None

        print("DIFICULDADE:", dificuldade)
        print("TIPO:", tipo)
        print("CONTEUDO:", conteudo)

        questoes = self.filtro.filtrar(
            questoes,
            conteudo=None,
            dificuldade=dificuldade,
            tipo=tipo
        )

        print("\n===== TOTAL FILTRADO =====")
        print(len(questoes))

        questoes = self.filtro.selecionar(
            questoes,
            quantidade=quantidade
        )

        print("\n===== TOTAL SELECIONADO =====")
        print(len(questoes))

        arquivo = self.pdf.gerar_atividade(
            questoes=questoes,
            disciplina=str(disciplina_id),
            titulo=titulo,
            conteudo=conteudo
        )

        return {
            "success": True,
            "quantidade": len(questoes),
            "arquivo": arquivo
        }