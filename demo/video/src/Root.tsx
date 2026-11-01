import { Composition } from "remotion";
import { Main } from "./Main";
import { T } from "./theme";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition id="Veil" component={Main} width={1920} height={1080} fps={T.fps} durationInFrames={T.total} />
  );
};
