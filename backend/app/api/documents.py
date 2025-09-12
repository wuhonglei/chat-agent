"""Document management endpoints"""

import os
import uuid
from typing import List

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from loguru import logger

from app.core.config import settings
from app.models.document import Document, DocumentResponse, DocumentSource, DocumentStatus
from app.services.document_processor import DocumentProcessor

router = APIRouter()


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
) -> DocumentResponse:
    """Upload and process a document"""
    try:
        # Validate file extension
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail=f"File type {file_extension} not supported")

        # Check file size
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File size {file_size_mb:.2f}MB exceeds limit of {settings.MAX_FILE_SIZE_MB}MB",
            )

        # Save file
        doc_id = str(uuid.uuid4())
        file_path = os.path.join(settings.UPLOAD_DIR, f"{doc_id}_{file.filename}")
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(file_content)

        # Process document
        processor = DocumentProcessor()
        document = await processor.process_file(file_path, doc_id, file.filename)

        # Add to vector store
        vector_store = request.app.state.vector_store
        chunk_ids = await vector_store.add_document(document)
        document.chunk_count = len(chunk_ids)

        logger.info(f"Document {file.filename} uploaded and processed successfully")

        return DocumentResponse(
            id=document.id,
            name=document.name,
            source=document.source.value,
            source_url=document.source_url,
            status=document.status.value,
            chunk_count=document.chunk_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to upload document: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import-url", response_model=DocumentResponse)
async def import_from_url(
    request: Request,
    url: str,
    source: DocumentSource,
) -> DocumentResponse:
    """Import document from external URL"""
    try:
        # Process external document
        processor = DocumentProcessor()
        document = await processor.process_url(url, source)

        # Add to vector store
        vector_store = request.app.state.vector_store
        chunk_ids = await vector_store.add_document(document)
        document.chunk_count = len(chunk_ids)

        logger.info(f"Document from {url} imported successfully")

        return DocumentResponse(
            id=document.id,
            name=document.name,
            source=document.source.value,
            source_url=document.source_url,
            status=document.status.value,
            chunk_count=document.chunk_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to import document from URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[DocumentResponse])
async def list_documents(request: Request) -> List[DocumentResponse]:
    """List all documents"""
    try:
        vector_store = request.app.state.vector_store
        documents = await vector_store.get_document_list()

        # Convert to response format
        return [
            DocumentResponse(
                id=doc["id"],
                name=doc["name"],
                source=doc["source"],
                source_url=None,  # TODO: Store and retrieve source URLs
                status=DocumentStatus.COMPLETED.value,
                chunk_count=doc["chunks"],
                created_at=datetime.now(),  # TODO: Store and retrieve timestamps
                updated_at=datetime.now(),
            )
            for doc in documents
        ]

    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(request: Request, document_id: str):
    """Delete a document"""
    try:
        vector_store = request.app.state.vector_store
        await vector_store.delete_document(document_id)

        # TODO: Also delete the physical file

        logger.info(f"Document {document_id} deleted successfully")
        return {"message": "Document deleted successfully"}

    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))
