import os
import requests
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("BERNOULLI_EMAIL")
PASSWORD = os.getenv("BERNOULLI_PASSWORD")


class BernoulliClient:

    def __init__(self):
        self.token = None

    def login(self):

        r = requests.post(
            "https://api.bernoulli.com.br/api/autenticacao/login",
            json={
                "email": EMAIL,
                "password": PASSWORD
            }
        )

        print("STATUS:", r.status_code)
        print("RESPOSTA:", r.text)

        r.raise_for_status()

        self.token = r.json()["access_token"]

        return self.token

    def headers(self):

        if not self.token:
            self.login()

        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Plataforma": "2",
            "Front-Version": "4.25.76"
        }

    def disciplinas(self):

        r = requests.get(
            "https://api.bernoulli.com.br/api/banco-de-questoes/subjects",
            headers=self.headers()
        )

        r.raise_for_status()

        return r.json()

    def conteudos(self, disciplina):

        disciplinas = self.disciplinas()["data"]

        for d in disciplinas:
            if str(d["id"]) == str(disciplina):
                return d.get("subitens", [])

        return []

    def questoes(
        self,
        page=1,
        per_page=20,
        disciplina=None
    ):

        params = {
            "page": page,
            "per_page": per_page
        }

        if disciplina:
            params["subjects"] = disciplina

        r = requests.get(
            "https://api.bernoulli.com.br/api/banco-de-questoes/questions",
            params=params,
            headers=self.headers()
        )

        r.raise_for_status()

        return r.json()