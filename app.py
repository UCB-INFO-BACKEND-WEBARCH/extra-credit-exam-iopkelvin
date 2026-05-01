import os
import uuid

from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue
from sqlalchemy import text

from models import db, Job


redis_conn = Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
queue = Queue("pipeline", connection=redis_conn)


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)

    with app.app_context():
        try:
            db.create_all()
        except Exception:
            db.session.rollback()

    @app.post("/jobs")
    def create_job():
        data = request.get_json(force=True)
        text_input = data.get("text", "")

        job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            status="pending",
            current_stage=1,
            failed_stage=None,
            error=None,
        )
        db.session.add(job)
        db.session.commit()

        queue.enqueue("worker.run_stage", job_id, 1, text_input)

        return jsonify({"job_id": job_id}), 202

    @app.get("/jobs/<job_id>")
    def get_job(job_id):
        job = Job.query.get(job_id)

        if job is None:
            return jsonify({"error": "not found"}), 404

        return jsonify({
            "job_id": job.id,
            "status": job.status,
            "current_stage": job.current_stage,
            "failed_stage": job.failed_stage,
            "error": job.error,
        }), 200

    @app.get("/health")
    def health():
        db_status = "down"
        redis_status = "down"
        volume_writable = False

        try:
            db.session.execute(text("SELECT 1"))
            db_status = "up"
        except Exception:
            pass

        try:
            redis_conn.ping()
            redis_status = "up"
        except Exception:
            pass

        try:
            test_path = os.path.join("/data", ".healthcheck")
            with open(test_path, "w") as f:
                f.write("ok")
            os.remove(test_path)
            volume_writable = True
        except Exception:
            volume_writable = False

        return jsonify({
            "status": "ok",
            "db": db_status,
            "redis": redis_status,
            "volume_writable": volume_writable,
        }), 200

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)