import { UploadOutlined, UserOutlined } from "@ant-design/icons";
import {
  Avatar,
  Button,
  Upload,
  type GetProp,
  type UploadFile,
  type UploadProps,
} from "antd";
import ImgCrop from "antd-img-crop";
import { useRef } from "react";
import { isValidAvatarImage } from "@/utils/image";

type FileType = Parameters<GetProp<UploadProps, "beforeUpload">>[0];

type Props = {
  value?: string;
  onChange?: (value: string) => void;
};

export default function AvatarUploader({ value, onChange }: Props) {
  const onPreview = async (file: UploadFile) => {
    let src = file.url as string;
    if (!src) {
      src = await new Promise(resolve => {
        const reader = new FileReader();
        reader.readAsDataURL(file.originFileObj as FileType);
        reader.onload = () => resolve(reader.result as string);
      });
    }
    const image = new Image();
    image.src = src;
    const imgWindow = window.open(src);
    imgWindow?.document.write(image.outerHTML);
  };

  return (
    <>
      <ImgCrop rotationSlider cropShape="round" beforeCrop={console.info}>
        <Upload
          pastable
          fileList={[]}
          onPreview={onPreview}
          onChange={console.warn}
          multiple={false}
          accept="image/*"
          beforeUpload={file => isValidAvatarImage(file)}
          action="https://660d2bd96ddfa2943b33731c.mockapi.io/api/upload"
        >
          {value ? (
            <Avatar
              size={64}
              src={value}
              icon={<UserOutlined />}
              className="cursor-pointer"
            />
          ) : (
            <Button icon={<UploadOutlined />}>上传头像</Button>
          )}
        </Upload>
      </ImgCrop>
    </>
  );
}
