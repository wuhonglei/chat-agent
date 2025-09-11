import React, { useState } from 'react'
import { Card, Tabs, Button, Modal, Input, Select, Form, message } from 'antd'
import { CloudUploadOutlined } from '@ant-design/icons'
import DocumentUpload from '../components/Document/DocumentUpload'
import DocumentList from '../components/Document/DocumentList'
import { useAppDispatch } from '../store/hooks'
import { importFromUrl } from '../store/slices/documentSlice'
import { DocumentSource } from '../types'

const { TabPane } = Tabs
const { Option } = Select

const DocumentsPage: React.FC = () => {
  const dispatch = useAppDispatch()
  const [importModalVisible, setImportModalVisible] = useState(false)
  const [importLoading, setImportLoading] = useState(false)
  const [form] = Form.useForm()

  const handleImportFromUrl = async (values: { url: string; source: DocumentSource }) => {
    setImportLoading(true)
    try {
      await dispatch(importFromUrl(values)).unwrap()
      message.success('文档导入成功')
      setImportModalVisible(false)
      form.resetFields()
    } catch (error: any) {
      message.error('导入失败: ' + error.message)
    } finally {
      setImportLoading(false)
    }
  }

  return (
    <div className="p-4">
      <Card>
        <div className="mb-4 flex justify-between items-center">
          <h1 className="text-xl font-semibold">文档管理</h1>
          <Button
            type="primary"
            icon={<CloudUploadOutlined />}
            onClick={() => setImportModalVisible(true)}
          >
            导入外部文档
          </Button>
        </div>

        <Tabs defaultActiveKey="list">
          <TabPane tab="文档列表" key="list">
            <DocumentList />
          </TabPane>
          <TabPane tab="上传文档" key="upload">
            <DocumentUpload />
          </TabPane>
        </Tabs>
      </Card>

      {/* Import Modal */}
      <Modal
        title="导入外部文档"
        open={importModalVisible}
        onCancel={() => setImportModalVisible(false)}
        footer={null}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleImportFromUrl}
        >
          <Form.Item
            name="source"
            label="文档来源"
            rules={[{ required: true, message: '请选择文档来源' }]}
          >
            <Select placeholder="选择文档来源">
              <Option value={DocumentSource.CONFLUENCE}>Confluence</Option>
              <Option value={DocumentSource.GOOGLE_DOCS}>Google Docs</Option>
              <Option value={DocumentSource.GOOGLE_SLIDES}>Google Slides</Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="url"
            label="文档链接"
            rules={[
              { required: true, message: '请输入文档链接' },
              { type: 'url', message: '请输入有效的URL' },
            ]}
          >
            <Input placeholder="https://..." />
          </Form.Item>

          <Form.Item className="mb-0">
            <Button
              type="primary"
              htmlType="submit"
              loading={importLoading}
              block
            >
              导入文档
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}

export default DocumentsPage