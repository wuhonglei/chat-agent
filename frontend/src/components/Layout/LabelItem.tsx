import { ConversationInfo } from "@/interfaces";
import { DeleteOutlined } from "@ant-design/icons";
import { Popconfirm } from "antd";
import styles from "./css/labelItem.module.css";
import classNames from "classnames";

type Props = {
  onDelete: (id: string) => void;
  conversation: ConversationInfo;
};

export default function LabelItem({ onDelete, conversation }: Props) {
  return (
    <div
      className={classNames(
        "h-10 w-full overflow-hidden flex items-center justify-between gap-2 relative",
        styles.container
      )}
    >
      <div
        title={conversation.title}
        className="w-full overflow-hidden text-ellipsis"
      >
        {conversation.title}
      </div>
      <Popconfirm
        title={null}
        okText="是"
        cancelText="否"
        icon={null}
        onCancel={e => {
          e?.stopPropagation();
        }}
        description="确定要删除吗？"
        onConfirm={e => {
          e?.stopPropagation();
          onDelete(conversation.id);
        }}
      >
        <DeleteOutlined
          onClick={e => {
            e?.stopPropagation();
          }}
          className={classNames(
            "invisible transition-opacity duration-300 absolute right-0",
            styles.operation
          )}
        />
      </Popconfirm>
    </div>
  );
}
