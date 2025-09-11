import React, { useCallback } from 'react'
import { Upload, message, Progress, UploadProps } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { RcFile } from 'antd/es/upload'
import { useAppDispatch, useAppSelector } from '../../store/hooks'
import { uploadDocument } from '../../store/slices/documentSlice'

const { Dragger } = Upload

const DocumentUpload: React.FC = () => {
  const dispatch = useAppDispatch()
  const { isUploading, uploadProgress } = useAppSelector((state) => state.document)

  const handleUpload = useCallback(async (file: RcFile) => {
    const allowedTypes = ['.pdf', '.docx', '.txt', '.md']
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase()
    
    if (!allowedTypes.includes(fileExtension)) {
      message.error(`不支持的文件类型: ${fileExtension}`)
      return false
    }

    const maxSize = 50 * 1024 * 1024 // 50MB
    if (file.size > maxSize) {
      message.error('文件大小不能超过 50MB')
      return false
    }

    try {
      await dispatch(uploadDocument(file as File)).unwrap()
      message.success('文档上传成功')
    } catch (error: any) {
      message.error('文档上传失败: ' + error.message)
    }
    
    return false // Prevent default upload
  }, [dispatch])

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    accept: '.pdf,.docx,.txt,.md',
    beforeUpload: handleUpload,
    showUploadList: false,
    disabled: isUploading,
  }

  return (
    <div className="p-4">
      <Dragger {...uploadProps} className="bg-gray-50">
        <p className="ant-upload-drag-icon">
          <InboxOutlined style={{ fontSize: 48, color: '#1890ff' }} />
        </p>
        <p className="ant-upload-text text-lg">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint text-gray-500">
          支持 PDF、Word、TXT、Markdown 格式，单个文件最大 50MB
        </p>
      </Dragger>
      
      {isUploading && (
        <div className="mt-4">
          <Progress percent={uploadProgress} status="active" />
        </div>
      )}
    </div>
  )
}

export default DocumentUpload