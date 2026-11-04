import { useState } from 'react'
import { uploadDataset } from '../services/api'

/**
 * Custom hook for handling file upload workflow.
 * Manages file state, format selection, and upload progress.
 * 
 * @returns {Object} Upload state and handlers
 */
export function useUpload() {
  const [files, setFiles] = useState({})
  const [format, setFormat] = useState('csv')
  const [datasetName, setDatasetName] = useState('')
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const setFile = (name, file) => {
    setFiles(prev => ({ ...prev, [name]: file }))
  }

  const clearFile = (name) => {
    setFiles(prev => {
      const updated = { ...prev }
      delete updated[name]
      return updated
    })
  }

  const upload = async (additionalData = {}) => {
    setUploading(true)
    setError(null)
    setResult(null)

    try {
      const formData = new FormData()
      formData.append('dataset_name', datasetName || 'Untitled Dataset')
      formData.append('format', format)
      
      Object.entries(files).forEach(([name, file]) => {
        formData.append(name, file)
      })

      Object.entries(additionalData).forEach(([key, value]) => {
        formData.append(key, value)
      })

      const response = await uploadDataset(formData)
      setResult(response)
      return response
    } catch (err) {
      setError(err.message || 'Upload failed')
      throw err
    } finally {
      setUploading(false)
    }
  }

  const reset = () => {
    setFiles({})
    setDatasetName('')
    setResult(null)
    setError(null)
  }

  return {
    files,
    format,
    datasetName,
    uploading,
    result,
    error,
    setFile,
    clearFile,
    setFormat,
    setDatasetName,
    upload,
    reset
  }
}
