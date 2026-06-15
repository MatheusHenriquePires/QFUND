from services.bernoulli import BernoulliClient


class ConteudosService:

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