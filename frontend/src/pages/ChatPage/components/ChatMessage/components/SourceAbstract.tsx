import { SearchSource } from "@/interfaces";
import { RightOutlined } from "@ant-design/icons";
import { isEmpty } from "lodash-es";
import CustomButton, {
  CustomButtonProps,
} from "@/components/common/CustomButton";
import SearchIcon from "@/assets/svg/SearchIcon.svg?react";
import classNames from "classnames";
import { Avatar, ConfigProvider } from "antd";
import { useWebIconUrls } from "@/hooks";
import React, { memo } from "react";

interface Props extends Omit<CustomButtonProps, "children"> {
  mode: "preSource" | "postSource";
  sources: SearchSource[] | undefined;
}

const maxIcons = 3;

const UrlIconGroup = memo(({ urlIcons }: { urlIcons: string[] }) => {
  if (isEmpty(urlIcons)) {
    return null;
  }

  return (
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
});

const SourceAbstract = ({ sources, mode, ...props }: Props) => {
  const urlIcons = useWebIconUrls(sources, {
    max: maxIcons,
  });

  if (isEmpty(sources)) {
    return null;
  }

  const icons = <UrlIconGroup urlIcons={urlIcons} />;
  const children =
    mode === "preSource" ? (
      <>
        <SearchIcon className="w-4 h-4 text-primary mr-1" />
        已阅读 {sources?.length} 个网页
        {icons}
      </>
    ) : (
      <>
        {icons}
        <span className="ml-1">{sources?.length} 个网页</span>
      </>
    );

  return (
    <CustomButton
      size="middle"
      {...props}
      className={classNames("text-gray-600", props.className)}
    >
      {children}
      <RightOutlined className="ml-1" />
    </CustomButton>
  );
};

export default React.memo(SourceAbstract);
