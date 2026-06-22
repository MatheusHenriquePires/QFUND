from bernoulli import BernoulliClient
import json

client = BernoulliClient()

q = client.questoes(per_page=1)["data"][0]

print(json.dumps(q, indent=2, ensure_ascii=False))