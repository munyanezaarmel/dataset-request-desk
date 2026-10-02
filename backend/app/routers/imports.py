from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_roles
from ..models import User
from ..services.importer import FileError, import_episodes

router = APIRouter(prefix="/episodes", tags=["import"])

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


@router.post("/import")
def import_csv(
    file: UploadFile = File(...),
    user: User = Depends(require_roles("operator", "admin")),
    db: Session = Depends(get_db),
):
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)  # read one byte too many to detect oversize files
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File too large (limit 50 MB)")
    try:
        return import_episodes(db, raw)
    except FileError as err:
        raise HTTPException(400, str(err))
    