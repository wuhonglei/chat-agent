import { SearchSource } from "@/types";
import { RightOutlined } from "@ant-design/icons";
import classNames from "classnames";
import { isEmpty } from "lodash-es";
import styles from "./css/SourceAbstract.module.css";

type Props = {
  onClick: () => void;
  sources: SearchSource[] | undefined;
};

export default function SourceAbstract({ sources, onClick }: Props) {
  if (isEmpty(sources)) {
    return null;
  }

  return (
    <section>
      <span
        onClick={onClick}
        className={classNames("py-2 px-2.5", styles["source-abstract"])}
      >
        {sources?.length} 篇资料
        <RightOutlined className="ml-1" />
      </span>
    </section>
  );
}
