import MarkdownContainer from "@/components/Chat/ChatMessage/components/MarkdownContainer";
import styles from "./index.module.css";
import simplify from "./raw/simplify.md?raw";
import reactMarkdown from "./raw/react-markdown.md?raw";
import { Tabs } from "antd";
import { useState } from "react";
import classNames from "classnames";

const items = [
  {
    key: "1",
    label: "Simplify",
  },
  {
    key: "2",
    label: "React Markdown",
  },
];

const content = {
  [items[0]?.key]: simplify,
  [items[1]?.key]: reactMarkdown,
};

export default function MarkdownPage() {
  const [activeKey, setActiveKey] = useState(items[0].key);

  return (
    <div className="flex flex-col h-full">
      <Tabs
        items={items}
        activeKey={activeKey}
        tabBarStyle={{ marginBottom: 0 }}
        onChange={key => setActiveKey(key)}
        style={{ paddingLeft: "32px" }}
      />
      <MarkdownContainer
        className={classNames(styles.container, "flex-1 py-8")}
      >
        {content[activeKey]}
      </MarkdownContainer>
    </div>
  );
}
