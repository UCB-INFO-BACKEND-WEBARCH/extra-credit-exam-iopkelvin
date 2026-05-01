"""rq worker entrypoint."""

import os
import json
import re
from collections import Counter

from redis import Redis
from rq import Queue, Worker
import time

from app import create_app
app = create_app(skip_db_create=True)
from models import db, Job, TopWord


DATA_DIR = "/data"

STOPWORDS = {"the", "a", "an", "and", "or", "but", "if", "then", "of",
             "in", "on", "at", "to", "for", "with", "by", "is", "are",
             "was", "were", "be", "been", "being", "this", "that"}

redis_conn = Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
queue = Queue("pipeline", connection=redis_conn)


def mark_running(job_id, stage):
    with app.app_context():
        job = Job.query.get(job_id)
        if job is not None:
            job.status = "running"
            job.current_stage = stage
            job.failed_stage = None
            job.error = None
            db.session.commit()


def mark_failed(job_id, stage, error):
    with app.app_context():
        job = Job.query.get(job_id)
        if job is not None:
            job.status = "failed"
            job.current_stage = stage
            job.failed_stage = stage
            job.error = str(error)
            db.session.commit()


def mark_completed(job_id):
    with app.app_context():
        job = Job.query.get(job_id)
        if job is not None:
            job.status = "completed"
            job.current_stage = 5
            job.failed_stage = None
            job.error = None
            db.session.commit()


def run_stage(job_id, stage, payload=None):
    try:
        mark_running(job_id, stage)
        time.sleep(1)

        job_path = os.path.join(DATA_DIR, job_id)
        os.makedirs(job_path, exist_ok=True)

        if stage == 1:
            if payload is None:
                raise ValueError("missing input text")

            with open(os.path.join(job_path, "stage1.txt"), "w") as f:
                f.write(payload)

        elif stage == 2:
            with open(os.path.join(job_path, "stage1.txt")) as f:
                data = f.read()

            with open(os.path.join(job_path, "stage2.txt"), "w") as f:
                f.write(data.lower())

        elif stage == 3:
            with open(os.path.join(job_path, "stage2.txt")) as f:
                data = f.read()

            tokens = [t for t in re.split(r"[\s\W_]+", data) if t]

            with open(os.path.join(job_path, "stage3.json"), "w") as f:
                json.dump(tokens, f)

        elif stage == 4:
            with open(os.path.join(job_path, "stage3.json")) as f:
                tokens = json.load(f)

            filtered = [t for t in tokens if t not in STOPWORDS]

            with open(os.path.join(job_path, "stage4.json"), "w") as f:
                json.dump(filtered, f)

        elif stage == 5:
            with open(os.path.join(job_path, "stage4.json")) as f:
                tokens = json.load(f)

            if not tokens:
                raise ValueError("no tokens remaining after stopword removal")

            counts = Counter(tokens)

            with open(os.path.join(job_path, "stage5.json"), "w") as f:
                json.dump(dict(counts), f)

            with app.app_context():
                TopWord.query.filter_by(job_id=job_id).delete()

                for word, count in counts.most_common(5):
                    db.session.add(TopWord(
                        job_id=job_id,
                        word=word,
                        count=count,
                    ))

                db.session.commit()

            mark_completed(job_id)
            return

        else:
            raise ValueError(f"invalid stage {stage}")

        queue.enqueue("worker.run_stage", job_id, stage + 1)

    except Exception as e:
        mark_failed(job_id, stage, e)


if __name__ == "__main__":
    Worker(["pipeline"], connection=redis_conn).work()