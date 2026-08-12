import uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file_storage):
    """Save an uploaded image under static/uploads with a random name.
    Returns the stored filename, or None if nothing valid was uploaded."""
    if not file_storage or not file_storage.filename:
        return None
    if not _allowed(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_storage.save(UPLOAD_DIR / filename)
    return filename


def delete_upload(filename):
    if not filename:
        return
    path = UPLOAD_DIR / filename
    if path.exists():
        path.unlink()
