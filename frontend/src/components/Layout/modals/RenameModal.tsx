import { validateTitle } from "@/utils/header";
import { Form, Input, Modal } from "antd";

type Props = {
  title: string;
  open: boolean;
  onCancel: () => void;
  onOk: (newTitle: string) => void;
};

export default function RenameModal({ title, open, onCancel, onOk }: Props) {
  const [form] = Form.useForm();
  const handleConfirm = async () => {
    const values = await form.validateFields();
    const newTitle = values.title as string;
    onOk(newTitle);
  };

  return (
    <Modal
      centered
      width={448}
      open={open}
      title="编辑对话名称"
      onCancel={onCancel}
      onOk={handleConfirm}
    >
      <Form form={form} onFinish={handleConfirm}>
        <Form.Item
          name="title"
          initialValue={title}
          rules={[
            {
              validator: (_, value) => {
                const error = validateTitle(value as string, title);
                return error ? Promise.reject(error) : Promise.resolve();
              },
            },
          ]}
        >
          <Input autoFocus />
        </Form.Item>
      </Form>
    </Modal>
  );
}
