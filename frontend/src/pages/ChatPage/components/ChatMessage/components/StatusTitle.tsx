import React from "react";

type Props = {
  titles: {
    doing: string;
    done: string;
  };
  isDoing: boolean;
};

const StatusTitle: React.FC<Props> = ({ titles, isDoing }) => {
  if (isDoing) {
    return <>{titles.doing}</>;
  }

  return <>{titles.done}</>;
};

export default React.memo(StatusTitle);
