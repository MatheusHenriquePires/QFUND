import copy
import queue
import threading
import time

from database import db


class QuestionPersistenceService:
    def __init__(self):
        self._queue = queue.Queue(maxsize=10_000)
        self._thread = threading.Thread(
            target=self._run,
            name="qfund-question-writer",
            daemon=True,
        )
        self._started = False
        self._start_lock = threading.Lock()
        self._stored = 0
        self._last_error = None
        self._last_write_at = None

    def enqueue(self, questions, discipline_id, series=None):
        items = copy.deepcopy(list(questions or []))
        if not items:
            return
        self._ensure_started()
        self._queue.put_nowait({
            "questions": items,
            "discipline_id": str(discipline_id or ""),
            "series": series,
        })

    def status(self):
        return {
            "ativo": self._thread.is_alive() if self._started else False,
            "lotes_pendentes": self._queue.qsize(),
            "questoes_gravadas": self._stored,
            "ultima_gravacao": self._last_write_at,
            "ultimo_erro": self._last_error,
        }

    def wait_until_empty(self, timeout=30):
        deadline = time.time() + timeout
        while self._queue.unfinished_tasks and time.time() < deadline:
            time.sleep(0.05)
        return self._queue.unfinished_tasks == 0

    def _ensure_started(self):
        if self._started:
            return
        with self._start_lock:
            if not self._started:
                self._thread.start()
                self._started = True

    def _run(self):
        while True:
            job = self._queue.get()
            try:
                total = db.upsert_questions_batch(
                    job["questions"],
                    discipline_id=job["discipline_id"],
                    series=job.get("series"),
                    download_images=True,
                )
                self._stored += total
                self._last_write_at = int(time.time())
                self._last_error = None
            except Exception as exc:
                self._last_error = str(exc)[:2000]
            finally:
                self._queue.task_done()


question_persistence_service = QuestionPersistenceService()
