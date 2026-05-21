/** Side-by-side before/after preview — thin composition of BeforeImage + AfterImage */

import { BeforeImage } from "./before-image";
import { AfterImage } from "./after-image";
import { STEP_LABELS } from "./step-selector";
import type { VignetteParams } from "../lib/vignette-geometry";
import type { FaceOvalParams } from "../lib/face-oval-geometry";

interface Props {
  originalUrl: string | null;
  images: Record<string, string>;
  selectedStep: string;
  onStepChange: (step: string) => void;
  faceOvalOverlayEnabled: boolean;
  faceOval: FaceOvalParams | null;
  onFaceOvalChange: (params: FaceOvalParams) => void;
  imageWidth: number;
  imageHeight: number;
  vignetteOverlayVisible: boolean;
  vignetteParams: VignetteParams;
  onVignetteParamChange: (path: string[], value: number) => void;
}

export function BeforeAfter({
  originalUrl,
  images,
  selectedStep,
  faceOvalOverlayEnabled,
  faceOval,
  onFaceOvalChange,
  imageWidth,
  imageHeight,
  vignetteOverlayVisible,
  vignetteParams,
  onVignetteParamChange,
}: Props) {
  const stepLabel = STEP_LABELS[selectedStep] ?? selectedStep;

  const showFaceOval =
    faceOvalOverlayEnabled &&
    (selectedStep === "face_corrected" || selectedStep === "final") &&
    imageWidth > 0 &&
    imageHeight > 0 &&
    faceOval !== null;

  return (
    <div className="flex gap-4 w-full">
      <BeforeImage originalUrl={originalUrl} />
      <AfterImage
        imageUrl={images[selectedStep] ?? null}
        stepLabel={stepLabel}
        faceOvalOverlayEnabled={showFaceOval}
        faceOval={faceOval}
        onFaceOvalChange={onFaceOvalChange}
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        vignetteOverlayVisible={vignetteOverlayVisible}
        vignetteParams={vignetteParams}
        onVignetteParamChange={onVignetteParamChange}
      />
    </div>
  );
}
