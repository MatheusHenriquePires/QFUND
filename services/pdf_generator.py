from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image
)

from reportlab.lib.styles import getSampleStyleSheet
from pathlib import Path
from datetime import datetime
import requests
import re
import os


class PDFGenerator:

    def __init__(self):
        self.output_dir = Path("generated/pdfs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.img_dir = Path("generated/images")
        self.img_dir.mkdir(parents=True, exist_ok=True)

    def limpar_html(self, texto):
        if not texto:
            return ""

        texto = re.sub(r"<[^>]+>", "", texto)

        html_entities = {
            "&nbsp;": " ",
            "&amp;": "&",
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"'
        }

        for k, v in html_entities.items():
            texto = texto.replace(k, v)

        return texto.strip()

    def gerar_atividade(self, questoes, disciplina, titulo="Atividade", conteudo=None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo = self.output_dir / f"atividade_{timestamp}.pdf"

        doc = SimpleDocTemplate(str(arquivo))
        styles = getSampleStyleSheet()
        elementos = []

        elementos.append(Paragraph("COLÉGIO PROPÓSITO", styles["Title"]))
        elementos.append(Paragraph(titulo, styles["Heading2"]))
        elementos.append(Spacer(1, 10))

        elementos.append(Paragraph(f"<b>Disciplina:</b> {disciplina}", styles["Normal"]))

        if conteudo:
            if isinstance(conteudo, list):
                conteudo_texto = ", ".join(map(str, conteudo))
            else:
                conteudo_texto = str(conteudo)
        else:
            conteudo_texto = "Todos"

        elementos.append(Paragraph(f"<b>Conteúdo:</b> {conteudo_texto}", styles["Normal"]))

        elementos.append(Spacer(1, 15))
        elementos.append(Paragraph("Aluno: _________________________________________", styles["Normal"]))
        elementos.append(Paragraph("Turma: _________________________________________", styles["Normal"]))
        elementos.append(Spacer(1, 20))

        for i, questao in enumerate(questoes, start=1):
            enunciado = questao.get("enunciado", "")
            elementos.append(Paragraph(f"<b>{i})</b> {enunciado}", styles["Normal"]))
            elementos.append(Spacer(1, 8))

            for url in questao.get("imagens", []):
                try:
                    resposta = requests.get(url, timeout=20)
                    resposta.raise_for_status()

                    nome_arquivo = os.path.basename(url.split("?")[0]) or f"imagem_{i}.png"
                    caminho_imagem = self.img_dir / nome_arquivo

                    with open(caminho_imagem, "wb") as f:
                        f.write(resposta.content)

                    elementos.append(Image(str(caminho_imagem), width=300, height=200))
                    elementos.append(Spacer(1, 10))

                except Exception as e:
                    print("Erro ao carregar imagem:", e)

            for alternativa in questao.get("alternativas", []):
                elementos.append(Paragraph(alternativa, styles["Normal"]))

            elementos.append(Spacer(1, 15))

        elementos.append(PageBreak())
        elementos.append(Paragraph("GABARITO", styles["Title"]))
        elementos.append(Spacer(1, 20))

        for i, questao in enumerate(questoes, start=1):
            resposta = questao.get("gabarito", "-")
            elementos.append(Paragraph(f"{i}) {resposta}", styles["Normal"]))

        doc.build(elementos)
        return str(arquivo)