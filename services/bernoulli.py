import os
import time
import json
import asyncio
import base64
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv("BERNOULLI_EMAIL")
PASSWORD = os.getenv("BERNOULLI_PASSWORD")
CACHE_TTL = int(os.getenv("BERNOULLI_CACHE_TTL", 3600))  # segundos


class BernoulliClient:

    def __init__(self):
        self.token = None
        self.session = requests.Session()
        # retries para erros transitórios
        retries = Retry(total=3, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # cabeçalhos padrões
        self.session.headers.update({
            "Accept": "application/json",
            "Plataforma": "2",
            "Front-Version": "4.25.76"
        })

        self._subjects_cache = None
        self._subjects_ts = 0
        self._etag = None
        self._token_expiry = None
        # cache em disco
        self._cache_path = Path(__file__).resolve().parent.parent / "generated" / "bernoulli_cache.json"
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # tentar carregar cache em disco
        self._load_cache()

    def _load_cache(self):
        try:
            if self._cache_path.exists():
                data = json.loads(self._cache_path.read_text(encoding="utf-8"))
                ts = data.get("ts", 0)
                if time.time() - ts < CACHE_TTL:
                    self._subjects_cache = data.get("subjects")
                    self._subjects_ts = ts
                    self._etag = data.get("etag")
        except Exception:
            self._subjects_cache = None

    def _save_cache(self, subjects):
        try:
            payload = {"ts": int(time.time()), "subjects": subjects, "etag": self._etag}
            self._cache_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def login(self):
        r = self.session.post(
            "https://api.bernoulli.com.br/api/autenticacao/login",
            json={
                "email": EMAIL,
                "password": PASSWORD
            },
            timeout=10
        )

        r.raise_for_status()

        resp = r.json()
        self.token = resp.get("access_token")

        # set expiry se disponível
        expires_in = resp.get("expires_in") or resp.get("expires")
        if expires_in:
            try:
                self._token_expiry = int(time.time()) + int(expires_in)
            except Exception:
                pass

        # tentar decodificar JWT para descobrir exp
        if self.token and not self._token_expiry:
            try:
                parts = self.token.split('.')
                if len(parts) > 1:
                    payload = parts[1]
                    missing_padding = len(payload) % 4
                    if missing_padding:
                        payload += '=' * (4 - missing_padding)
                    decoded = base64.urlsafe_b64decode(payload)
                    payload_json = json.loads(decoded)
                    exp = payload_json.get('exp')
                    if exp:
                        self._token_expiry = int(exp)
            except Exception:
                pass

        if self.token:
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})

        return self.token

    def _request(self, method, url, **kwargs):
        # Faz a requisição e, em caso de 401, tenta relogar uma vez
        if "timeout" not in kwargs:
            kwargs["timeout"] = 10
        # refresh proativo do token
        if not self.token:
            self.login()
        else:
            if self._token_expiry and time.time() >= (self._token_expiry - 60):
                self.login()

        r = self.session.request(method, url, **kwargs)

        if r.status_code == 401:
            # token expirou ou inválido: relogar e tentar novamente
            self.login()
            r = self.session.request(method, url, **kwargs)

        r.raise_for_status()
        return r

    def disciplinas(self):
        # retorna cache em memória se válido
        if self._subjects_cache and (time.time() - self._subjects_ts < CACHE_TTL):
            return self._subjects_cache

        # se cache em disco válido foi carregado no __init__, use-o
        if self._subjects_cache:
            return self._subjects_cache

        url = "https://api.bernoulli.com.br/api/banco-de-questoes/subjects"

        headers = {}
        if self._etag:
            headers["If-None-Match"] = self._etag

        r = self.session.get(url, headers=headers, timeout=10)
        if r.status_code == 304:
            return self._subjects_cache

        if r.status_code == 401:
            self.login()
            r = self.session.get(url, headers=headers, timeout=10)

        r.raise_for_status()
        data = r.json()

        # salvar cache e etag
        try:
            self._subjects_cache = data
            self._subjects_ts = int(time.time())
            self._etag = r.headers.get("ETag")
            self._save_cache(data)
        except Exception:
            pass

        return data

    def conteudos(self, disciplina):
        disciplinas = self.disciplinas().get("data", [])

        for d in disciplinas:
            if str(d.get("id")) == str(disciplina):
                return d.get("subitens", [])

        return []

    def questoes(
        self,
        page=1,
        per_page=20,
        disciplina=None,
        fetch_all=False
    ):

        params = {
            "page": page,
            "per_page": per_page
        }

        if disciplina:
            params["subjects"] = disciplina

        # Se solicitado, buscar todas as páginas de forma concorrente (async)
        if fetch_all:
            try:
                return asyncio.run(self._fetch_all_questions_async(disciplina=disciplina, per_page=per_page))
            except Exception:
                # fallback para requisição síncrona caso algo dê errado
                r = self._request(
                    "GET",
                    "https://api.bernoulli.com.br/api/banco-de-questoes/questions",
                    params=params
                )

                return r.json()

        r = self._request(
            "GET",
            "https://api.bernoulli.com.br/api/banco-de-questoes/questions",
            params=params
        )

        return r.json()

    async def _fetch_all_questions_async(self, disciplina, per_page=100, max_concurrency=8):
        import httpx

        url = "https://api.bernoulli.com.br/api/banco-de-questoes/questions"

        headers = dict(self.session.headers)

        async def _get_with_retries(client, p):
            backoff = 0.5
            for attempt in range(3):
                try:
                    r = await client.get(url, params={"page": p, "per_page": per_page})
                    if r.status_code == 429:
                        await asyncio.sleep(backoff)
                        backoff *= 2
                        continue
                    r.raise_for_status()
                    return r.json()
                except Exception:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(backoff)
                    backoff *= 2

        async with httpx.AsyncClient(headers=headers, timeout=10) as client:
            # primeira página
            first = await _get_with_retries(client, 1)
            data_list = first.get("data", [])

            # tentar obter total de páginas via meta
            meta = first.get("meta") or first.get("pagination") or {}
            last_page = None
            if isinstance(meta, dict):
                last_page = meta.get("last_page") or meta.get("total_pages") or meta.get("pages")
                if not last_page and meta.get("total") and per_page:
                    try:
                        total = int(meta.get("total"))
                        last_page = (total + per_page - 1) // per_page
                    except Exception:
                        last_page = None

            if last_page and last_page > 1:
                pages = list(range(2, last_page + 1))
                sem = asyncio.Semaphore(max_concurrency)

                async def bounded(p):
                    async with sem:
                        res = await _get_with_retries(client, p)
                        return res.get("data", [])

                tasks = [asyncio.create_task(bounded(p)) for p in pages]
                results = await asyncio.gather(*tasks)
                for r in results:
                    data_list.extend(r)

                return {"data": data_list}

            # se não há meta, buscar em chunks até não retornar mais dados
            page = 2
            while True:
                chunk = list(range(page, page + max_concurrency))
                tasks = [asyncio.create_task(_get_with_retries(client, p)) for p in chunk]
                responses = await asyncio.gather(*tasks)
                any_found = False
                for resp in responses:
                    items = resp.get("data", [])
                    if items:
                        any_found = True
                        data_list.extend(items)
                if not any_found:
                    break
                page += max_concurrency

            return {"data": data_list}