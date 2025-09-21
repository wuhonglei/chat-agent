import { SearchSource } from "@/types";
import { RightOutlined } from "@ant-design/icons";
import { isEmpty } from "lodash-es";
import CustomButton, { CustomButtonProps } from "@/components/CustomButton";
import SearchIcon from "@/assets/svg/SearchIcon.svg?react";
import classNames from "classnames";
import { Avatar, ConfigProvider } from "antd";
import { useWebIconUrls } from "@/hooks";

interface Props extends Omit<CustomButtonProps, "children"> {
  mode: "preSource" | "postSource";
  sources: SearchSource[] | undefined;
}

const maxIcons = 3;

export default function SourceAbstract({ sources, mode, ...props }: Props) {
  const urlIcons = useWebIconUrls(sources, maxIcons);
  if (isEmpty(sources)) {
    return null;
  }

  const urlIconsGroup = (
    <ConfigProvider
      theme={{ components: { Avatar: { groupBorderColor: "transparent" } } }}
    >
      <Avatar.Group size={16} max={{ count: maxIcons }} className="ml-1">
        {urlIcons.map((url: string, index: number) => (
          <Avatar
            style={{ backgroundColor: "#fff" }}
            key={index}
            src={url}
            className="bg-white"
          />
        ))}
      </Avatar.Group>
    </ConfigProvider>
  );

  const children =
    mode === "preSource" ? (
      <>
        <SearchIcon className="w-4 h-4 text-blue-500 mr-1" />
        已阅读 {sources?.length} 篇资料
        {urlIconsGroup}
      </>
    ) : (
      <>
        {urlIconsGroup}
        {sources?.length} 篇资料
      </>
    );

  return (
    <CustomButton
      {...props}
      className={classNames("text-gray-600", props.className)}
      size="small"
    >
      {children}
      <RightOutlined className="ml-1" />
    </CustomButton>
  );
}
