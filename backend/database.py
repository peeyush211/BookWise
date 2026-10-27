import os
import pandas as pd
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session
from .config import Config
from .models.database_models import Base, Book, User, Rating, Favorite, ReadingListItem, FeedbackEvent

def _create_engine(database_url):
    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine = _create_engine(Config.SQLALCHEMY_DATABASE_URI)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


def configure_database(database_url):
    """Rebind the session factory, primarily for app factories and tests."""
    global engine, SessionLocal
    SessionLocal.remove()
    engine = _create_engine(database_url)
    SessionLocal.configure(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _book_from_row(row):
    """Build a catalogue row without changing existing user-owned records."""

    return Book(
        book_id=int(row["book_id"]),
        goodreads_book_id=int(row.get("goodreads_book_id", 0)),
        best_book_id=int(row.get("best_book_id", 0)),
        work_id=int(row.get("work_id", 0)),
        books_count=int(row.get("books_count", 1)),
        isbn=str(row.get("isbn", "")) if pd.notna(row.get("isbn")) else None,
        isbn13=str(row.get("isbn13", "")) if pd.notna(row.get("isbn13")) else None,
        authors=str(row.get("authors", "Unknown")),
        original_publication_year=int(row.get("original_publication_year", 0)),
        original_title=str(row.get("original_title", row.get("title", ""))),
        title=str(row.get("title", "")),
        language_code=str(row.get("language_code", "eng")),
        average_rating=float(row.get("average_rating", 0.0)),
        ratings_count=int(row.get("ratings_count", 0)),
        work_ratings_count=int(row.get("work_ratings_count", 0)),
        work_text_reviews_count=int(row.get("work_text_reviews_count", 0)),
        ratings_1=int(row.get("ratings_1", 0)),
        ratings_2=int(row.get("ratings_2", 0)),
        ratings_3=int(row.get("ratings_3", 0)),
        ratings_4=int(row.get("ratings_4", 0)),
        ratings_5=int(row.get("ratings_5", 0)),
        image_url=str(row.get("image_url", "")),
        small_image_url=str(row.get("small_image_url", "")),
        primary_genre=str(row.get("primary_genre", "Fiction")),
        top_tags=str(row.get("top_tags", "")),
        weighted_rating=float(row.get("weighted_rating", 0.0)),
        has_valid_cover=bool(row.get("has_valid_cover", True))
    )


def sync_catalog():
    """Insert missing catalogue books from the canonical processed CSV.

    This is idempotent: existing books and all user-owned data are preserved.
    """

    csv_path = Config.BOOKS_CSV
    if not os.path.exists(csv_path):
        print(f"Warning: Clean books CSV not found at {csv_path}")
        return 0

    books_df = pd.read_csv(csv_path)
    db = SessionLocal()
    inserted = 0
    try:
        existing_ids = {book_id for (book_id,) in db.query(Book.book_id).all()}
        batch = []
        for _, row in books_df.iterrows():
            book_id = int(row["book_id"])
            if book_id in existing_ids:
                continue
            batch.append(_book_from_row(row))
            existing_ids.add(book_id)
            if len(batch) >= 1000:
                db.bulk_save_objects(batch)
                db.commit()
                inserted += len(batch)
                batch = []
        if batch:
            db.bulk_save_objects(batch)
            db.commit()
            inserted += len(batch)
        print(f"Catalog sync complete: inserted {inserted:,} missing books; CSV contains {len(books_df):,} books.")
        return inserted
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _ensure_catalog_schema():
    """Align legacy catalogue columns with the current SQLAlchemy model."""

    if engine.dialect.name != "postgresql":
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE books ALTER COLUMN authors TYPE TEXT"))
        connection.execute(text("ALTER TABLE books ALTER COLUMN top_tags TYPE TEXT"))


def init_db():
    """Create all tables and synchronize missing books from the processed CSV."""
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    try:
        _ensure_catalog_schema()
        sync_catalog()
    except Exception as exc:
        print(f"Error in init_db: {exc}")
