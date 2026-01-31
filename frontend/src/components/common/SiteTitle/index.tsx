import { Typography } from "antd";
import { WEB_TITLE } from "@/constants";
import type { TitleProps } from "antd/es/typography/Title";

const { Title } = Typography;

type Props = {
  level?: TitleProps["level"];
  style?: React.CSSProperties;
};

export default function SiteTitle({ level = 5, style }: Props) {
  return (
    <Title level={level} style={{ marginBottom: 0, letterSpacing: 1, ...style }}>
      {WEB_TITLE}
    </Title>
  );
}
