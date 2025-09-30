import React from "react";
import { Typography } from "antd";
const { Title } = Typography;
import classNames from "classnames";

type Props = {
  className?: string;
  children?: React.ReactNode;
};

export default function WelcomePage({ children, className }: Props) {
  return (
    <div className={classNames("flex flex-col gap-4 items-center", className)}>
      <Title level={3} className="flex items-center gap-4">
        有什么我能帮你的吗？
      </Title>
      {children}
    </div>
  );
}
