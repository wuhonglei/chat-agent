import { SourceData } from "@/types";
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

export default function SourceSider({ sourceData, onClose }: Props) {
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
            <span>参考资料</span>
            <Button type="text" icon={<CloseOutlined />} onClick={onClose} />
          </div>
        }
        className="h-full overflow-y-auto"
        style={{ borderRadius: 0 }}
        styles={{
          body: { padding: "16px" },
        }}
      >
        <SourceCard sources={sourceData?.sources} />
      </Card>
    </Layout.Sider>
  );
}
