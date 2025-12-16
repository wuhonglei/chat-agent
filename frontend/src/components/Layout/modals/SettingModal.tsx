import { UserInfo } from "@/interfaces";
import { userAPI } from "@/services";
import { useAppDispatch } from "@/store/hooks";
import { setUserInfo } from "@/store/slices/userSlice";
import { useRequest } from "ahooks";
import { App, Form, Input, Modal } from "antd";
import { isEqual, pick } from "lodash-es";
import { useEffect } from "react";
import AvatarUploader from "./AvatarUploader";

type Props = {
  open: boolean;
  onCancel: () => void;
  data: UserInfo | null;
};

export default function SettingModal({ open, onCancel, data }: Props) {
  const [form] = Form.useForm<UserInfo>();
  const { message } = App.useApp();
  const dispatch = useAppDispatch();
  const { run: updateUserInfo, loading } = useRequest(userAPI.updateUserInfo, {
    manual: true,
    onSuccess: data => {
      message.success("更新成功");
      dispatch(setUserInfo(data));
      setTimeout(() => {
        onCancel();
      }, 300);
    },
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue(data);
    }
  }, [data, form]);

  const handleConfirm = async () => {
    const values = await form.validateFields();
    const currentKeys = Object.keys(values);
    const initialData = pick(data, currentKeys);
    if (isEqual(initialData, values)) {
      message.warning("没有修改");
      return;
    }
    updateUserInfo(values);
  };

  return (
    <Modal
      centered
      open={open}
      title="用户设置"
      onCancel={onCancel}
      onOk={handleConfirm}
      okButtonProps={{ loading }}
    >
      <Form
        form={form}
        layout="horizontal"
        labelCol={{ span: 4 }}
        wrapperCol={{ span: 8 }}
      >
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
        <Form.Item label="手机号" name="phone">
          <Input placeholder="请输入手机号" disabled />
        </Form.Item>
        <Form.Item label="头像" name="avatar">
          <AvatarUploader />
        </Form.Item>
      </Form>
    </Modal>
  );
}
