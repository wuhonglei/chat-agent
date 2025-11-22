import { UploadOutlined, UserOutlined } from "@ant-design/icons";
import { Avatar, Button, Upload, type GetProp, type UploadProps } from "antd";
import ImgCrop from "antd-img-crop";
import { isValidAvatarImage } from "@/utils/image";
import { useRequest } from "ahooks";
import { fileAPI } from "@/services/file";
import { App } from "antd";

type CustomRequestOptions = Parameters<
  GetProp<UploadProps, "customRequest">
>[0];

type Props = {
  value?: string;
  onChange?: (value: string) => void;
};

export default function AvatarUploader({ value, onChange }: Props) {
  const { message } = App.useApp();
  const { run, loading } = useRequest(fileAPI.uploadAvatar, {
    manual: true,
    onSuccess: url => {
      message.success("上传成功");
      onChange?.(url);
    },
    onError: () => {
      message.error("上传失败");
    },
  });
  const customRequest = async (options: CustomRequestOptions) => {
    const { file } = options;
    run(file as File);
  };

  return (
    <>
      <ImgCrop rotationSlider cropShape="round" beforeCrop={console.info}>
        <Upload
          pastable
          fileList={[]}
          multiple={false}
          accept="image/*"
          // action={"/api/file/upload_avatar"}
          customRequest={customRequest}
          beforeUpload={file => isValidAvatarImage(file)}
        >
          {value ? (
            <Avatar
              size={64}
              src={value}
              icon={<UserOutlined />}
              className="cursor-pointer"
            />
          ) : (
            <Button icon={<UploadOutlined />} loading={loading}>
              上传头像
            </Button>
          )}
        </Upload>
      </ImgCrop>
    </>
  );
}
