import React from "react";
import { SourceData } from "@/interfaces";
import { Layout } from "antd";
import { isEmpty } from "lodash-es";
import { Card } from "antd";
import { CloseOutlined } from "@ant-design/icons";
import { Button } from "antd";
import SourceCard from "./SourceCard";

type Props = {
  onClose: () => void;
  sourceData: SourceData | undefined;
};

const SourceSider = ({ sourceData, onClose }: Props) => {
  return (
    <Layout.Sider
      width={400}
      theme="light"
      trigger={null}
      collapsedWidth={0}
      collapsed={isEmpty(sourceData)}
      className="shadow-md flex flex-col items-center overflow-hidden"
    >
      <Card
        title={
          <div className="flex items-center justify-between">
            <span>搜索结果</span>
            <Button type="text" icon={<CloseOutlined />} onClick={onClose} />
          </div>
        }
        className="h-full overflow-y-auto flex flex-col"
        style={{ borderRadius: 0 }}
        styles={{
          body: {
            padding: 8,
            width: 400,
            flex: 1,
            height: 0,
            overflowY: "auto",
            gap: 6,
          },
        }}
      >
        {sourceData?.sources.map((source, index) => (
          <SourceCard source={source} rank={index + 1} key={index} />
        ))}
      </Card>
    </Layout.Sider>
  );
};

export default React.memo(SourceSider);
