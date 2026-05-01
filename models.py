"""SQLAlchemy models — student stub.

Define at minimum:
  - Job(id, status, current_stage, failed_stage?, error?, created_at, updated_at)
  - TopWord(job_id, word, count)

You may add more columns/tables as needed.
"""
# TODO: define Job and TopWord models
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.String, primary_key=True)
    status = db.Column(db.String, nullable=False, default="pending")
    current_stage = db.Column(db.Integer, nullable=False, default=1)
    failed_stage = db.Column(db.Integer, nullable=True)
    error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TopWord(db.Model):
    __tablename__ = "top_words"

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.String, db.ForeignKey("jobs.id"), nullable=False)
    word = db.Column(db.Text, nullable=False)
    count = db.Column(db.Integer, nullable=False)