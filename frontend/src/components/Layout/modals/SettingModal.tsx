import { useEffect } from "react";
import { Form, Input, Modal } from "antd";
import { UserInfo } from "@/interfaces";
import AvatarUploader from "./AvatarUploader";

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
    <Modal open={open} onCancel={onCancel} title="用户设置">
      <Form
        form={form}
        layout="horizontal"
        labelCol={{ span: 4 }}
        wrapperCol={{ span: 8 }}
      >
        <Form.Item name="id" hidden>
          <Input disabled />
        </Form.Item>
        <Form.Item
          label="用户名"
          name="name"
          rules={[
            { required: true, message: "请输入用户名" },
            { min: 3, message: "用户名至少3位" },
            { max: 16, message: "用户名最多16位" },
          ]}
        >
          <Input placeholder="请输入用户名" />
        </Form.Item>
        <Form.Item label="头像" name="avatar">
          <AvatarUploader />
        </Form.Item>
      </Form>
    </Modal>
  );
}
