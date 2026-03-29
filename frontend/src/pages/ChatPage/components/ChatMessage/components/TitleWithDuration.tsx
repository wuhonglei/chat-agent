import React from "react";

type Props = {
  titles: {
    doing: string;
    done: string;
  };
  isDoing: boolean;
};

const TitleWithDuration: React.FC<Props> = ({ titles, isDoing }) => {
  if (isDoing) {
    return <>{titles.doing}</>;
  }

  return <>{titles.done}</>;
};

export default React.memo(TitleWithDuration);
