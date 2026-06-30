import threading
import time

from database import db
from services.bernoulli import BernoulliClient
from services.parser_questoes import QuestaoParser


class QuestionSyncService:
    PER_PAGE = 100
    GRADE_CODES = (
        "EF1", "EF2", "EF3", "EF4", "EF5", "EF6", "EF7",
        "EF8", "EF9", "EM1", "EM2", "EM3",
    )

    def __init__(self):
        self.client = BernoulliClient()
        self.parser = QuestaoParser()
        self._lock = threading.Lock()
        self._thread = None

    def start_background(self, download_images=True, classify_grades=True):
        if self._thread and self._thread.is_alive():
            raise ValueError("Já existe uma sincronização em andamento")
        run_id = db.start_sync_run(0)
        self._thread = threading.Thread(
            target=self.sync_all,
            kwargs={
                "run_id": run_id,
                "download_images": download_images,
                "classify_grades": classify_grades,
            },
            name="qfund-question-sync",
            daemon=True,
        )
        self._thread.start()
        return run_id

    def sync_all(
        self,
        run_id=None,
        download_images=True,
        classify_grades=True,
        progress=None,
    ):
        if not self._lock.acquire(blocking=False):
            raise ValueError("Já existe uma sincronização em andamento")

        try:
            response = self.client.disciplinas()
            subjects = response.get("data", []) if isinstance(response, dict) else response
            if not subjects:
                raise RuntimeError("A API não retornou disciplinas")

            run_id = run_id or db.start_sync_run(len(subjects))
            db.update_sync_run(
                run_id, total_disciplines=len(subjects), phase="catalog",
            )
            db.sync_catalog(subjects)

            seen = 0
            unique_ids = set()
            for index, subject in enumerate(subjects, start=1):
                discipline_id = str(subject.get("id"))
                discipline_name = subject.get("name") or discipline_id
                db.update_sync_run(
                    run_id,
                    phase="questions",
                    current_discipline=discipline_name,
                    current_grade=None,
                    completed_disciplines=index - 1,
                )

                for raw_batch in self._iterate_page_batches(discipline_id):
                    parsed_batch = [self.parser.parse(item) for item in raw_batch]
                    db.upsert_questions_batch(
                        parsed_batch,
                        discipline_id=discipline_id,
                        download_images=download_images,
                    )
                    seen += len(raw_batch)
                    unique_ids.update(
                        (discipline_id, str(item.get("id"))) for item in raw_batch
                    )
                    self._report(
                        run_id, progress, "questions", discipline_name,
                        None, index - 1, seen, len(unique_ids),
                    )

                db.update_sync_run(run_id, completed_disciplines=index)

            if classify_grades:
                seen = self._classify_all_grades(
                    subjects, run_id, seen, unique_ids, progress, download_images
                )

            stats = db.bank_statistics()
            db.update_sync_run(
                run_id,
                status="completed",
                phase="completed",
                current_discipline=None,
                current_grade=None,
                completed_disciplines=len(subjects),
                questions_seen=seen,
                questions_stored=stats["questoes"],
                images_stored=stats["imagens"],
                finished_at=int(time.time()),
            )
            if progress:
                progress({"run_id": run_id, "status": "completed", **stats})
            return {"run_id": run_id, "status": "completed", **stats}
        except Exception as exc:
            if run_id:
                db.update_sync_run(
                    run_id,
                    status="failed",
                    phase="failed",
                    error=str(exc)[:2000],
                    finished_at=int(time.time()),
                )
            raise
        finally:
            self._lock.release()

    def _classify_all_grades(
        self, subjects, run_id, seen, unique_ids, progress, download_images
    ):
        for subject_index, subject in enumerate(subjects, start=1):
            discipline_id = str(subject.get("id"))
            discipline_name = subject.get("name") or discipline_id
            for grade_code in self.GRADE_CODES:
                db.update_sync_run(
                    run_id,
                    phase="grades",
                    current_discipline=discipline_name,
                    current_grade=grade_code,
                    completed_disciplines=subject_index - 1,
                )
                for raw_batch in self._iterate_page_batches(discipline_id, grade_code):
                    missing = db.link_external_questions_grade(
                        discipline_id,
                        [item.get("id") for item in raw_batch],
                        grade_code,
                    )
                    if missing:
                        missing_set = set(missing)
                        parsed_batch = [
                            self.parser.parse(item) for item in raw_batch
                            if str(item.get("id")) in missing_set
                        ]
                        db.upsert_questions_batch(
                            parsed_batch,
                            discipline_id=discipline_id,
                            download_images=download_images,
                        )
                        db.link_external_questions_grade(
                            discipline_id, missing, grade_code
                        )
                        unique_ids.update(
                            (discipline_id, value) for value in missing
                        )
                    seen += len(raw_batch)

                self._report(
                    run_id, progress, "grades", discipline_name, grade_code,
                    subject_index - 1, seen, len(unique_ids),
                )
        return seen

    def _iterate_page_batches(self, discipline_id, grade_code=None):
        page = 1
        total_pages = None
        while total_pages is None or page <= total_pages:
            response = self._request_page(discipline_id, page, grade_code)
            items = response.get("data", [])
            if not items:
                break

            meta = response.get("meta") or response.get("pagination") or {}
            if total_pages is None:
                total_pages = self._total_pages(meta, len(items))

            yield items

            if len(items) < self.PER_PAGE:
                break
            page += 1
            if page > 10000:
                raise RuntimeError("Paginação excedeu o limite de segurança")

    def _request_page(self, discipline_id, page, grade_code):
        last_error = None
        for attempt in range(1, 9):
            try:
                return self.client.questoes(
                    disciplina=discipline_id,
                    page=page,
                    per_page=self.PER_PAGE,
                    fetch_all=False,
                    serie=grade_code,
                )
            except Exception as exc:
                last_error = exc
                if attempt == 8:
                    break
                time.sleep(min(2 ** attempt, 60))
        raise RuntimeError(
            f"Falha ao buscar disciplina {discipline_id}, série {grade_code or '-'}, "
            f"página {page}, após 8 tentativas: {last_error}"
        ) from last_error

    def _total_pages(self, meta, returned):
        for key in ("total_pages", "last_page", "pages"):
            if meta.get(key) is not None:
                try:
                    return max(1, int(meta[key]))
                except (TypeError, ValueError):
                    pass
        try:
            total = int(meta.get("total"))
            return max(1, (total + self.PER_PAGE - 1) // self.PER_PAGE)
        except (TypeError, ValueError):
            return 1 if returned < self.PER_PAGE else None

    def _report(
        self, run_id, progress, phase, discipline, grade,
        completed_disciplines, seen, stored,
    ):
        stats = db.bank_statistics()
        db.update_sync_run(
            run_id,
            phase=phase,
            current_discipline=discipline,
            current_grade=grade,
            completed_disciplines=completed_disciplines,
            questions_seen=seen,
            questions_stored=stats["questoes"],
            images_stored=stats["imagens"],
        )
        if progress:
            progress({
                "run_id": run_id,
                "phase": phase,
                "discipline": discipline,
                "grade": grade,
                "questions_seen": seen,
                "questions_stored": stats["questoes"],
                "images_stored": stats["imagens"],
            })


question_sync_service = QuestionSyncService()
