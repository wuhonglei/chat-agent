"""Knowledge base management endpoints"""

import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from loguru import logger

router = APIRouter()


@router.get("/export")
async def export_knowledge_base(request: Request):
    """Export knowledge base as downloadable file"""
    try:
        vector_store = request.app.state.vector_store
        
        # Get all documents
        documents = await vector_store.get_document_list()
        
        # Create zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add metadata file
            metadata = {
                "export_date": datetime.now().isoformat(),
                "document_count": len(documents),
                "documents": documents,
            }
            zip_file.writestr("metadata.json", json.dumps(metadata, indent=2))
            
            # TODO: Add actual document contents and vectors
            
        zip_buffer.seek(0)
        
        return StreamingResponse(
            io.BytesIO(zip_buffer.read()),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=knowledge_base_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to export knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/import")
async def import_knowledge_base(request: Request):
    """Import knowledge base from uploaded file"""
    try:
        # TODO: Implement knowledge base import
        raise HTTPException(status_code=501, detail="Knowledge base import not implemented yet")
        
    except Exception as e:
        logger.error(f"Failed to import knowledge base: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/share")
async def create_share_link(request: Request):
    """Create a shareable link for the knowledge base"""
    try:
        # TODO: Implement sharing functionality
        # This would generate a unique link that others can use to access the knowledge base
        raise HTTPException(status_code=501, detail="Knowledge base sharing not implemented yet")
        
    except Exception as e:
        logger.error(f"Failed to create share link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_knowledge_base_stats(request: Request):
    """Get knowledge base statistics"""
    try:
        vector_store = request.app.state.vector_store
        documents = await vector_store.get_document_list()
        
        total_chunks = sum(doc['chunks'] for doc in documents)
        
        return {
            "document_count": len(documents),
            "total_chunks": total_chunks,
            "sources": {
                "local": len([d for d in documents if d['source'] == 'local']),
                "confluence": len([d for d in documents if d['source'] == 'confluence']),
                "google_docs": len([d for d in documents if d['source'] == 'google_docs']),
                "google_slides": len([d for d in documents if d['source'] == 'google_slides']),
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get knowledge base stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))