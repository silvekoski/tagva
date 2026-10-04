import { Composition, Still } from "remotion";
import { ReadmeHeader } from "./scenes/readme-header";
import { scenes } from "./catalog";

const fps = 30;

export function Root() {
  return (
    <>
      {scenes.map((s) => (
        <Composition key={s.id} id={s.id} component={s.component} durationInFrames={s.seconds * fps} fps={fps} width={1920} height={1080} defaultProps={s.overlay === undefined ? {} : { overlay: s.overlay }} />
      ))}
      <Still id="readme-header" component={ReadmeHeader} width={1920} height={640} />
    </>
  );
}
