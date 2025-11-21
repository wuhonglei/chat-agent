import React, { useEffect } from "react";
import { Button, Form, Input, Modal, Upload } from "antd";
import { UserInfo } from "@/interfaces";
import { UploadOutlined } from "@ant-design/icons";

type Props = {
  open: boolean;
  onCancel: () => void;
  data: UserInfo | null;
};

export default function SettingModal({ open, onCancel, data }: Props) {
  const [form] = Form.useForm<UserInfo>();

  useEffect(() => {
    if (data) {
      form.setFieldsValue(data);
    }
  }, [data, form]);

  return (
    <Modal open={open} onCancel={onCancel} title="设置">
      <Form form={form} layout="vertical">
        <Form.Item name="id" hidden>
          <Input disabled />
        </Form.Item>
        <Form.Item label="用户名" name="name">
          <Input />
        </Form.Item>
        <Form.Item label="头像" name="avatar">
          <Upload>
            <Button icon={<UploadOutlined />}>上传头像</Button>
          </Upload>
        </Form.Item>
      </Form>
    </Modal>
  );
}
