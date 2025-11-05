import os
import shutil
from typing import List, Optional
from uuid import uuid4

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from database import db, create_document, get_documents
from schemas import Vehicle

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure uploads directory exists and mount it for static serving
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
def read_root():
    return {"message": "Car Marketplace API"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Helper to serialize Mongo documents
from bson import ObjectId

def serialize_vehicle(doc: dict):
    return {
        "id": str(doc.get("_id")) if doc.get("_id") else None,
        "make": doc.get("make"),
        "model": doc.get("model"),
        "year": doc.get("year"),
        "price": doc.get("price"),
        "description": doc.get("description"),
        "image_urls": doc.get("image_urls", []),
        "created_at": doc.get("created_at"),
    }


@app.get("/vehicles")
async def list_vehicles():
    try:
        docs = get_documents("vehicle", {}, None)
        return [serialize_vehicle(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vehicles")
async def create_vehicle(
    make: str = Form(...),
    model: str = Form(...),
    year: int = Form(...),
    price: float = Form(...),
    description: Optional[str] = Form(None),
    images: Optional[List[UploadFile]] = File(None),
):
    # Save uploaded images and build public URLs
    image_urls: List[str] = []
    if images:
        for img in images:
            filename = img.filename or f"image-{uuid4().hex}"
            ext = os.path.splitext(filename)[1] or ".jpg"
            safe_name = f"{uuid4().hex}{ext}"
            dest_path = os.path.join(UPLOAD_DIR, safe_name)
            try:
                with open(dest_path, "wb") as buffer:
                    shutil.copyfileobj(img.file, buffer)
                image_urls.append(f"/uploads/{safe_name}")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to save image: {str(e)}")

    vehicle = Vehicle(
        make=make,
        model=model,
        year=year,
        price=price,
        description=description,
        image_urls=image_urls,
    )

    try:
        inserted_id = create_document("vehicle", vehicle)
        return {"id": inserted_id, **vehicle.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
