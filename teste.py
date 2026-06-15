from pdf_generator import PDFGenerator

pdf = PDFGenerator()

questoes = [
    {
        "statement": """
        <p>Qual é a capital do Brasil?</p>

        A) São Paulo<br>
        B) Brasília<br>
        C) Rio de Janeiro
        """,
        "correctAnswer": "B"
    },
    {
        "statement": """
        <p>Quanto é 2 + 2?</p>

        A) 3<br>
        B) 4<br>
        C) 5
        """,
        "correctAnswer": "B"
    }
]

arquivo = pdf.gerar_atividade(
    titulo="Atividade Teste",
    disciplina="Matemática",
    conteudo="Operações Básicas",
    questoes=questoes
)

print(arquivo)