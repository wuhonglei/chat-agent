import AvatarUploader from "@/components/common/AvatarUploader";
import { userAPI } from "@/services";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { setUserInfo } from "@/store/slices/userSlice";
import { useRequest } from "ahooks";
import { App, Space, Typography } from "antd";
import { useCallback } from "react";

export default function AccountManage() {
  const data = useAppSelector(state => state.user.userDetail);
  const { message } = App.useApp();
  const dispatch = useAppDispatch();
  const { run: updateUserInfo, loading: nameLoading } = useRequest(
    (payload: { avatar?: string; name?: string }) => userAPI.updateUserInfo(payload),
    {
      manual: true,
      onSuccess: res => {
        message.success("更新成功");
        dispatch(setUserInfo(res));
      },
    }
  );

  const handleNameChange = (value: string) => {
    const name = value?.trim() ?? "";
    if (!name) {
      message.error("请输入用户名");
      return;
    }
    if (name.length < 3) {
      message.error("用户名至少3位");
      return;
    }
    if (name.length > 16) {
      message.error("用户名最多16位");
      return;
    }
    // 是否变化
    if (name === data?.name) {
      return;
    }
    updateUserInfo({ name });
  };

  return (
    <Space orientation="vertical" size={16} style={{ width: "100%", maxWidth: 520 }}>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-0">
        <Typography.Text type="secondary">用户名</Typography.Text>
        <Typography.Paragraph
          editable={
            !nameLoading
              ? {
                  onChange: handleNameChange,
                }
              : false
          }
          style={{ marginBottom: 0 }}
        >
          {data?.name || "请输入用户名"}
        </Typography.Paragraph>
      </div>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-0">
        <Typography.Text type="secondary">手机号</Typography.Text>
        <Typography.Text type="secondary">{data?.phone}</Typography.Text>
      </div>
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between sm:gap-0">
        <Typography.Text type="secondary">头像</Typography.Text>
        <AvatarUploaderWithAutoSave value={data?.avatar} onUploadComplete={url => updateUserInfo({ avatar: url })} />
      </div>
    </Space>
  );
}

function AvatarUploaderWithAutoSave({
  value,
  onChange,
  onUploadComplete,
}: {
  value?: string;
  onChange?: (v: string) => void;
  onUploadComplete: (url: string) => void;
}) {
  const handleChange = useCallback(
    (url: string) => {
      onChange?.(url);
      onUploadComplete(url);
    },
    [onChange, onUploadComplete]
  );
  return <AvatarUploader value={value} onChange={handleChange} />;
}
