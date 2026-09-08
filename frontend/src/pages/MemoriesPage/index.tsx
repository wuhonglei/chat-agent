import DataManage from "@/components/Layout/components/DataManage";
import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Typography } from "antd";
import { Link } from "react-router-dom";

export default function MemoriesPage() {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-gray-200 px-4 py-3">
        <Link to="/chat">
          <Button type="text" icon={<ArrowLeftOutlined />}>
            返回对话
          </Button>
        </Link>
        <Typography.Title level={4} style={{ margin: 0 }}>
          记忆管理
        </Typography.Title>
      </div>
      <div className="flex-1 overflow-auto p-4">
        <DataManage />
      </div>
    </div>
  );
}
