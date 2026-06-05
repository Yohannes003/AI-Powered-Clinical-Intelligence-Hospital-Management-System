from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.db.session import get_icu_db

router = APIRouter(prefix="/icu", tags=["ICU Integration"])


@router.get("/status")
async def icu_status(db=Depends(get_icu_db)):
    """Check connectivity to the ICU monitoring database."""
    try:
        result = await db.execute(text("SELECT 1"))
        _ = result.scalar()
        return {"status": "connected", "message": "ICU DB reachable"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ICU DB connection failed: {e}")
