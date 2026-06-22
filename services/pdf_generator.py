from html import escape
from pathlib import Path
from datetime import datetime
import hashlib
import os
import re
import unicodedata

import requests
from bs4 import BeautifulSoup
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)


class PDFGenerator:

    PAGE_WIDTH, PAGE_HEIGHT = A4
    LOGO_PATH = Path("assets/logo_proposito.png")
    AZUL_PROP = colors.HexColor("#183A7D")
    AMARELO_PROP = colors.HexColor("#F5C400")
    BORDA_PROP = colors.HexColor("#35539A")

    def __init__(self):
        self.output_dir = Path("generated/pdfs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.img_dir = Path("generated/images")
        self.img_dir.mkdir(parents=True, exist_ok=True)

    def limpar_html(self, texto):
        if not texto:
            return ""

        texto = BeautifulSoup(texto, "html.parser").get_text("\n")
        texto = texto.replace("\xa0", " ")
        texto = re.sub(r"\n{3,}", "\n\n", texto)

        return texto.strip()

    def gerar_atividade(
        self,
        questoes,
        disciplina,
        titulo="Atividade",
        conteudo=None,
        incluir_gabarito=False,
        professor=None,
        data_avaliacao=None
    ):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        arquivo = self.output_dir / f"atividade_{timestamp}.pdf"
        self._titulo_cabecalho = str(titulo or "Atividade").upper()
        self._disciplina_cabecalho = str(disciplina or "").upper()
        self._disciplina_resposta = self._normalizar_texto(disciplina)
        self._professor_cabecalho = str(professor or "CARLOS EDUARDO").upper()
        self._data_cabecalho = self._formatar_data_avaliacao(data_avaliacao)

        doc = BaseDocTemplate(
            str(arquivo),
            pagesize=A4,
            leftMargin=12 * mm,
            rightMargin=12 * mm,
            topMargin=55 * mm,
            bottomMargin=20 * mm,
            title=titulo,
            author="QFUND",
        )
        self._configurar_paginas(doc)

        elementos = []
        styles = self._criar_estilos()

        if not questoes:
            elementos.append(Paragraph(
                "Nenhuma questão encontrada para os filtros selecionados.",
                styles["questao"],
            ))
            self._adicionar_linhas_resposta(elementos, quantidade=2)

        for i, questao in enumerate(questoes, start=1):
            self._adicionar_questao(elementos, styles, questao, i, doc.width)

        if incluir_gabarito:
            elementos.append(PageBreak())
            elementos.append(Paragraph("GABARITO", styles["gabarito_titulo"]))
            elementos.append(Spacer(1, 6 * mm))

            for i, questao in enumerate(questoes, start=1):
                resposta = self._texto_seguro(questao.get("gabarito", "-"))
                elementos.append(
                    Paragraph(f"{i}) {resposta or '-'}", styles["Normal"])
                )

        doc.build(elementos)

        return str(arquivo)

    def _criar_estilos(self):
        styles = getSampleStyleSheet()

        styles.add(ParagraphStyle(
            name="questao",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=15,
            alignment=TA_LEFT,
            spaceAfter=3,
        ))

        styles.add(ParagraphStyle(
            name="alternativa",
            parent=styles["questao"],
            leftIndent=7 * mm,
            firstLineIndent=-5 * mm,
            spaceAfter=2,
        ))

        styles.add(ParagraphStyle(
            name="gabarito_titulo",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            alignment=TA_CENTER,
            spaceAfter=5,
        ))

        styles["Normal"].fontName = "Helvetica"
        styles["Normal"].fontSize = 12
        styles["Normal"].leading = 15

        return styles

    def _adicionar_questao(self, elementos, styles, questao, numero, largura):
        enunciado_original = self.limpar_html(str(questao.get("enunciado", "")))
        enunciado = self._texto_seguro(enunciado_original)
        texto = f"{numero}. {enunciado}" if enunciado else f"{numero}."

        elementos.append(Paragraph(texto, styles["questao"]))
        elementos.append(Spacer(1, 2 * mm))

        for url in questao.get("imagens", []):
            imagem = self._criar_imagem(url, largura)
            if imagem:
                elementos.append(imagem)
                elementos.append(Spacer(1, 4 * mm))

        alternativas = questao.get("alternativas", [])
        for alternativa in alternativas:
            elementos.append(
                Paragraph(self._texto_seguro(alternativa), styles["alternativa"])
            )

        if not alternativas and "___" not in enunciado_original:
            self._adicionar_area_resposta(elementos, enunciado_original)

        elementos.append(Spacer(1, 5 * mm))

    def _adicionar_area_resposta(self, elementos, enunciado):
        perfil = self._perfil_resposta(enunciado)

        if perfil == "calculo":
            self._adicionar_espaco_calculo(elementos)
            return

        if perfil == "curta":
            self._adicionar_linhas_resposta(elementos, quantidade=2)
            return

        quantidade = 6 if self._pede_resposta_longa(enunciado) else 4
        self._adicionar_linhas_resposta(elementos, quantidade=quantidade)

    def _adicionar_linhas_resposta(self, elementos, quantidade=4):
        for _ in range(quantidade):
            elementos.append(Spacer(1, 5 * mm))
            elementos.append(HRFlowable(
                width="100%",
                thickness=0.45,
                color=colors.HexColor("#777777"),
                spaceBefore=0,
                spaceAfter=0,
            ))

    def _adicionar_espaco_calculo(self, elementos):
        elementos.append(Spacer(1, 26 * mm))
        elementos.append(HRFlowable(
            width="100%",
            thickness=0.45,
            color=colors.HexColor("#999999"),
            spaceBefore=0,
            spaceAfter=0,
        ))

    def _perfil_resposta(self, enunciado):
        texto = self._normalizar_texto(enunciado)

        if self._pede_calculo(texto):
            return "calculo"

        if self._disciplina_resposta in {
            "matematica",
            "fisica",
            "quimica",
        }:
            return "calculo"

        if self._pede_resposta_curta(texto):
            return "curta"

        return "linhas"

    def _pede_calculo(self, texto):
        termos = (
            "calcule",
            "calcular",
            "resolva",
            "resolver",
            "determine",
            "determinar",
            "efetue",
            "simplifique",
            "desenvolva a expressao",
            "arme",
            "equacao",
            "area",
            "perimetro",
            "volume",
            "velocidade",
            "forca",
            "energia",
            "massa",
            "densidade",
            "concentracao",
        )
        return any(termo in texto for termo in termos)

    def _pede_resposta_longa(self, enunciado):
        texto = self._normalizar_texto(enunciado)
        termos = (
            "explique",
            "justifique",
            "descreva",
            "argumente",
            "compare",
            "analise",
            "interprete",
            "comente",
            "produza",
            "redija",
            "relacione",
            "por que",
        )
        return any(termo in texto for termo in termos)

    def _pede_resposta_curta(self, texto):
        termos = (
            "complete",
            "cite",
            "identifique",
            "indique",
            "nomeie",
            "classifique",
            "assinale",
            "marque",
            "qual e",
            "quais sao",
        )
        return any(termo in texto for termo in termos)

    def _criar_imagem(self, url, largura_disponivel):
        try:
            caminho_imagem = self._obter_imagem(url)
            reader = ImageReader(str(caminho_imagem))
            largura_original, altura_original = reader.getSize()

            largura_maxima = min(largura_disponivel * 0.82, 150 * mm)
            altura_maxima = 70 * mm
            escala = min(
                largura_maxima / largura_original,
                altura_maxima / altura_original,
                1,
            )

            imagem = Image(
                str(caminho_imagem),
                width=largura_original * escala,
                height=altura_original * escala,
            )
            imagem.hAlign = "CENTER"

            return imagem

        except Exception as e:
            print("Erro ao carregar imagem:", e)
            return None

    def _obter_imagem(self, url):
        if not url:
            raise ValueError("URL de imagem vazia")

        if str(url).startswith(("http://", "https://")):
            nome_base = os.path.basename(url.split("?")[0]) or "imagem.png"
            extensao = Path(nome_base).suffix or ".png"
            digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
            caminho_imagem = self.img_dir / f"{digest}{extensao}"

            if caminho_imagem.exists() and caminho_imagem.stat().st_size > 0:
                return caminho_imagem

            resposta = requests.get(
                url,
                headers={"User-Agent": "QFUND PDF Generator"},
                timeout=(3, 6),
            )
            resposta.raise_for_status()
            caminho_imagem.write_bytes(resposta.content)

            return caminho_imagem

        caminho = Path(url)
        if not caminho.exists():
            raise FileNotFoundError(url)

        return caminho

    def _desenhar_pagina(self, canvas, doc):
        canvas.saveState()
        self._desenhar_cabecalho(canvas)
        self._desenhar_rodape(canvas, doc)
        canvas.restoreState()

    def _desenhar_pagina_sem_cabecalho(self, canvas, doc):
        canvas.saveState()
        self._desenhar_rodape(canvas, doc)
        canvas.restoreState()

    def _configurar_paginas(self, doc):
        largura_frame = self.PAGE_WIDTH - doc.leftMargin - doc.rightMargin

        primeira_pagina = Frame(
            doc.leftMargin,
            doc.bottomMargin,
            largura_frame,
            self.PAGE_HEIGHT - doc.topMargin - doc.bottomMargin,
            id="primeira_pagina",
            showBoundary=0,
        )

        paginas_seguintes = Frame(
            doc.leftMargin,
            doc.bottomMargin,
            largura_frame,
            self.PAGE_HEIGHT - (14 * mm) - doc.bottomMargin,
            id="paginas_seguintes",
            showBoundary=0,
        )

        doc.addPageTemplates([
            PageTemplate(
                id="primeira",
                frames=[primeira_pagina],
                onPage=self._desenhar_pagina,
                autoNextPageTemplate="seguintes",
            ),
            PageTemplate(
                id="seguintes",
                frames=[paginas_seguintes],
                onPage=self._desenhar_pagina_sem_cabecalho,
            ),
        ])

    def _desenhar_cabecalho(self, canvas):
        margem_x = 10 * mm
        topo = self.PAGE_HEIGHT - 8 * mm
        largura = self.PAGE_WIDTH - 20 * mm

        canvas.setFillColor(self.AZUL_PROP)
        canvas.setFont("Helvetica", 18)
        titulo = self._texto_limitado_canvas(
            canvas,
            self._titulo_cabecalho,
            135 * mm,
            "Helvetica",
            18,
        )
        canvas.drawString(margem_x, topo - 9 * mm, titulo)

        canvas.setStrokeColor(self.AMARELO_PROP)
        canvas.setLineWidth(5)
        canvas.line(margem_x + 1 * mm, topo - 15 * mm, margem_x + 137 * mm, topo - 15 * mm)

        logo_x = margem_x + 145 * mm
        canvas.setStrokeColor(self.AZUL_PROP)
        canvas.setLineWidth(1.2)
        canvas.line(logo_x - 4 * mm, topo - 18 * mm, logo_x - 4 * mm, topo + 1 * mm)
        self._desenhar_logo_proposito(canvas, logo_x, topo - 20 * mm)

        y_aluno = topo - 32 * mm
        self._campo_retangular(
            canvas,
            margem_x,
            y_aluno,
            largura - 35 * mm,
            10 * mm,
            "ALUNO(A)",
            "",
            valor_font_size=9,
        )
        self._campo_retangular(
            canvas,
            margem_x + largura - 33 * mm,
            y_aluno,
            33 * mm,
            10 * mm,
            "DATA",
            self._data_cabecalho,
            valor_font_size=8.5,
        )

        y_info = topo - 45 * mm
        gap = 1.5 * mm
        col1 = 53 * mm
        col2 = 39 * mm
        col3 = 49 * mm
        col4 = largura - col1 - col2 - col3 - (3 * gap)

        x = margem_x
        self._campo_retangular(canvas, x, y_info, col1, 10 * mm, "ANO/SÉRIE/CURSO", "5EFI")
        x += col1 + gap
        self._campo_turno(canvas, x, y_info, col2, 10 * mm)
        x += col2 + gap
        self._campo_retangular(
            canvas,
            x,
            y_info,
            col3,
            10 * mm,
            "DISCIPLINA",
            self._disciplina_cabecalho or "DISCIPLINA",
        )
        x += col3 + gap
        self._campo_retangular(
            canvas,
            x,
            y_info,
            col4,
            10 * mm,
            "PROFESSOR(A)",
            self._professor_cabecalho,
        )

    def _desenhar_logo_proposito(self, canvas, x, y):
        if not self.LOGO_PATH.exists():
            return

        try:
            logo = ImageReader(str(self.LOGO_PATH))
            canvas.drawImage(
                logo,
                x,
                y,
                width=48 * mm,
                height=18 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception as e:
            print("Erro ao desenhar logo:", e)

    def _campo_retangular(self, canvas, x, y, largura, altura, rotulo, valor, valor_font_size=8.5):
        canvas.setStrokeColor(self.BORDA_PROP)
        canvas.setLineWidth(0.7)
        canvas.roundRect(x, y, largura, altura, 2, stroke=1, fill=0)

        canvas.setFillColor(colors.white)
        canvas.rect(x + 3 * mm, y + altura - 2.5 * mm, 16 * mm + len(rotulo) * 1.15, 4 * mm, stroke=0, fill=1)

        canvas.setFillColor(self.AZUL_PROP)
        canvas.setFont("Helvetica-Bold", 8)
        canvas.drawString(x + 3 * mm, y + altura - 1.4 * mm, rotulo)

        canvas.setFillColor(colors.black)
        canvas.setFont("Helvetica-Bold", valor_font_size)
        texto = self._texto_limitado_canvas(canvas, str(valor or ""), largura - 8 * mm, "Helvetica-Bold", valor_font_size)
        canvas.drawCentredString(x + largura / 2, y + 3 * mm, texto)

    def _campo_turno(self, canvas, x, y, largura, altura):
        self._campo_retangular(canvas, x, y, largura, altura, "TURNO", "", valor_font_size=8)
        canvas.setStrokeColor(self.AZUL_PROP)
        canvas.setLineWidth(0.7)
        canvas.circle(x + 8 * mm, y + 4.2 * mm, 1.5 * mm, stroke=1, fill=0)
        canvas.circle(x + 22 * mm, y + 4.2 * mm, 1.5 * mm, stroke=1, fill=0)
        canvas.setFillColor(self.AZUL_PROP)
        canvas.setFont("Helvetica", 6.5)
        canvas.drawString(x + 10 * mm, y + 3.1 * mm, "MANHÃ")
        canvas.drawString(x + 24 * mm, y + 3.1 * mm, "TARDE")

    def _draw_string_limitado(self, canvas, x, y, texto, largura_maxima):
        original = str(texto or "")
        texto = original
        while texto and canvas.stringWidth(texto, "Helvetica-Bold", 9) > largura_maxima:
            texto = texto[:-1]

        if texto != original:
            texto = texto[:-3].rstrip() + "..."

        canvas.drawString(x, y, texto)

    def _texto_limitado_canvas(self, canvas, texto, largura_maxima, fonte, tamanho):
        original = str(texto or "")
        texto = original
        while texto and canvas.stringWidth(texto, fonte, tamanho) > largura_maxima:
            texto = texto[:-1]

        if texto != original and len(texto) > 3:
            texto = texto[:-3].rstrip() + "..."

        return texto

    def _formatar_data_avaliacao(self, data_avaliacao):
        if isinstance(data_avaliacao, datetime):
            return data_avaliacao.strftime("%d/%m/%Y")

        if data_avaliacao:
            texto = str(data_avaliacao).strip()
            for formato in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(texto, formato).strftime("%d/%m/%Y")
                except ValueError:
                    pass
            return texto

        return datetime.now().strftime("%d/%m/%Y")

    def _desenhar_rodape(self, canvas, doc):
        margem_x = 12 * mm
        y = 8 * mm

        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            self.PAGE_WIDTH - margem_x,
            y + 3 * mm,
            str(doc.page),
        )

    def _texto_seguro(self, texto):
        texto = self.limpar_html(str(texto or ""))
        texto = escape(texto)
        texto = texto.replace("\n", "<br/>")

        return texto

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
