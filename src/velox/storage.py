from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DB_URL = "sqlite:///velox.db"


class Base(DeclarativeBase):
    pass


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario: Mapped[str] = mapped_column(String)
    duration: Mapped[float] = mapped_column(Float)
    workers: Mapped[int] = mapped_column(Integer)
    ramp_up: Mapped[float] = mapped_column(Float, default=0.0)
    results: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


_engine = create_engine(DB_URL)
Base.metadata.create_all(_engine)


def save_benchmark(
    scenario: str,
    duration: float,
    workers: int,
    ramp_up: float,
    results: dict,
) -> Benchmark:
    """
    Persist a completed benchmark run.

    :param scenario: Name of the benchmark scenario.
    :param duration: Benchmark duration in seconds.
    :param workers: Number of concurrent workers.
    :param ramp_up: Ramp-up duration in seconds.
    :param results: Metrics snapshot to store as JSON.
    :returns: The persisted benchmark row
    """
    with Session(_engine, expire_on_commit=False) as session:
        benchmark = Benchmark(
            scenario=scenario,
            duration=duration,
            workers=workers,
            ramp_up=ramp_up,
            results=results,
        )
        session.add(benchmark)
        session.commit()
        return benchmark


def list_benchmarks() -> list[Benchmark]:
    """
    Load all persisted benchmarks, newest first.

    :returns: List of benchmark rows ordered by creation time descending.
    """
    with Session(_engine) as session:
        return session.query(Benchmark).order_by(Benchmark.created_at.desc()).all()
