import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit'
import { documentAPI } from '../../services/api'
import { Document, DocumentSource } from '../../types'

interface DocumentState {
  documents: Document[]
  isLoading: boolean
  isUploading: boolean
  uploadProgress: number
  error: string | null
  stats: {
    document_count: number
    total_chunks: number
    sources: {
      local: number
      confluence: number
      google_docs: number
      google_slides: number
    }
  }
}

const initialState: DocumentState = {
  documents: [],
  isLoading: false,
  isUploading: false,
  uploadProgress: 0,
  error: null,
  stats: {
    document_count: 0,
    total_chunks: 0,
    sources: {
      local: 0,
      confluence: 0,
      google_docs: 0,
      google_slides: 0,
    },
  },
}

// Async thunks
export const fetchDocuments = createAsyncThunk(
  'document/fetchDocuments',
  async () => {
    const response = await documentAPI.getDocuments()
    return response.data
  }
)

export const uploadDocument = createAsyncThunk(
  'document/uploadDocument',
  async (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    const response = await documentAPI.uploadDocument(formData)
    return response.data
  }
)

export const deleteDocument = createAsyncThunk(
  'document/deleteDocument',
  async (documentId: string) => {
    await documentAPI.deleteDocument(documentId)
    return documentId
  }
)

export const importFromUrl = createAsyncThunk(
  'document/importFromUrl',
  async ({ url, source }: { url: string; source: DocumentSource }) => {
    const response = await documentAPI.importFromUrl(url, source)
    return response.data
  }
)

const documentSlice = createSlice({
  name: 'document',
  initialState,
  reducers: {
    setUploadProgress: (state, action: PayloadAction<number>) => {
      state.uploadProgress = action.payload
    },
    clearError: (state) => {
      state.error = null
    },
    updateStats: (state, action: PayloadAction<DocumentState['stats']>) => {
      state.stats = action.payload
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch documents
      .addCase(fetchDocuments.pending, (state) => {
        state.isLoading = true
        state.error = null
      })
      .addCase(fetchDocuments.fulfilled, (state, action) => {
        state.isLoading = false
        state.documents = action.payload
      })
      .addCase(fetchDocuments.rejected, (state, action) => {
        state.isLoading = false
        state.error = action.error.message || 'Failed to fetch documents'
      })
      // Upload document
      .addCase(uploadDocument.pending, (state) => {
        state.isUploading = true
        state.uploadProgress = 0
        state.error = null
      })
      .addCase(uploadDocument.fulfilled, (state, action) => {
        state.isUploading = false
        state.uploadProgress = 100
        state.documents.push(action.payload)
      })
      .addCase(uploadDocument.rejected, (state, action) => {
        state.isUploading = false
        state.uploadProgress = 0
        state.error = action.error.message || 'Failed to upload document'
      })
      // Delete document
      .addCase(deleteDocument.fulfilled, (state, action) => {
        state.documents = state.documents.filter(
          (doc) => doc.id !== action.payload
        )
      })
      // Import from URL
      .addCase(importFromUrl.pending, (state) => {
        state.isUploading = true
        state.error = null
      })
      .addCase(importFromUrl.fulfilled, (state, action) => {
        state.isUploading = false
        state.documents.push(action.payload)
      })
      .addCase(importFromUrl.rejected, (state, action) => {
        state.isUploading = false
        state.error = action.error.message || 'Failed to import document'
      })
  },
})

export const { setUploadProgress, clearError, updateStats } = documentSlice.actions

export default documentSlice.reducer