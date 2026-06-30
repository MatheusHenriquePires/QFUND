import argparse
import json

from services.question_sync_service import question_sync_service


def print_progress(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sincroniza todo o banco de questões Bernoulli")
    parser.add_argument("--sem-imagens", action="store_true", help="Não baixa as imagens")
    parser.add_argument("--sem-series", action="store_true", help="Não classifica EF1-EM3")
    args = parser.parse_args()

    result = question_sync_service.sync_all(
        download_images=not args.sem_imagens,
        classify_grades=not args.sem_series,
        progress=print_progress,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
