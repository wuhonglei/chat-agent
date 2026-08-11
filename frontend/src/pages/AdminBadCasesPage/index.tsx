import { ArrowLeftOutlined } from "@ant-design/icons";
import { Button, Tabs, Typography } from "antd";
import React from "react";
import { Link } from "react-router-dom";
import BadCasesTab from "./BadCasesTab";
import EvalRunLogsTab from "./EvalRunLogsTab";

const AdminBadCasesPage: React.FC = () => {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 border-b border-gray-200 px-4 py-3">
        <Link to="/chat">
          <Button type="text" icon={<ArrowLeftOutlined />}>
            返回对话
          </Button>
        </Link>
        <Typography.Title level={4} style={{ margin: 0 }}>
          Bad Case 复核
        </Typography.Title>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <Tabs
          defaultActiveKey="bad-cases"
          items={[
            {
              key: "bad-cases",
              label: "Bad Case",
              children: <BadCasesTab />,
            },
            {
              key: "run-logs",
              label: "评估历史",
              children: <EvalRunLogsTab />,
            },
          ]}
        />
      </div>
    </div>
  );
};

export default AdminBadCasesPage;
