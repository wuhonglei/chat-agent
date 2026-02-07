import AvatarUploader from "@/components/common/AvatarUploader";
import { UserInfo } from "@/interfaces";
import { userAPI } from "@/services";
import { useAppDispatch } from "@/store/hooks";
import { setUserInfo } from "@/store/slices/userSlice";
import { useRequest } from "ahooks";
import { App, Form, Input } from "antd";
import { isEqual, pick } from "lodash-es";
import { forwardRef, useEffect, useImperativeHandle, useRef } from "react";

export type AccountManageRef = {
  submit: () => Promise<void>;
};

type Props = {
  data: UserInfo | null;
  onSuccess?: (data: UserInfo) => void;
  onLoadingChange?: (loading: boolean) => void;
};

const AccountManage = forwardRef<AccountManageRef, Props>(function AccountManage(
  { data, onSuccess, onLoadingChange },
  ref
) {
  const [form] = Form.useForm<UserInfo>();
  const { message } = App.useApp();
  const dispatch = useAppDispatch();
  const { run: updateUserInfo, loading } = useRequest(userAPI.updateUserInfo, {
    manual: true,
    onSuccess: res => {
      message.success("更新成功");
      dispatch(setUserInfo(res));
      onSuccess?.(res);
    },
  });

  const dataRef = useRef(data);
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  useEffect(() => {
    if (data) {
      form.setFieldsValue(data);
    }
  }, [data, form]);

  useEffect(() => {
    onLoadingChange?.(loading);
  }, [loading, onLoadingChange]);

  const handleConfirm = async () => {
    const values = await form.validateFields();
    const currentKeys = Object.keys(values);
    const initialData = pick(dataRef.current, currentKeys);
    if (isEqual(initialData, values)) {
      message.warning("没有修改");
      return;
    }
    updateUserInfo(values);
  };

  useImperativeHandle(ref, () => ({
    submit: handleConfirm,
  }));

  return (
    <Form form={form} layout="horizontal" labelCol={{ span: 4 }} wrapperCol={{ span: 8 }}>
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
  );
});

export default AccountManage;
