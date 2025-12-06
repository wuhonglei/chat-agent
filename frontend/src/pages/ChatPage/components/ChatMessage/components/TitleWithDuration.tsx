import React from "react";

type Props = {
  titles: {
    doing: string;
    done: string;
  };
  isDoing: boolean;
  duration?: number;
};

const TitleWithDuration: React.FC<Props> = ({ titles, isDoing, duration }) => {
  if (isDoing) {
    return <>{titles.doing}</>;
  }
  if (!duration) {
    return <>{titles.done}</>;
  }

  return (
    <>
      {titles.done}
      <span className="ml-1 text-black-tertiary">{duration}s</span>
    </>
  );
};

export default React.memo(TitleWithDuration);
