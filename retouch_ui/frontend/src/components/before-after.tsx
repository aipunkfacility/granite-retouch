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
  vignetteOverlayEnabled: boolean;
  faceOvalOverlayEnabled: boolean;
  faceOval: FaceOvalParams | null;
  onFaceOvalChange: (params: FaceOvalParams) => void;
  imageWidth: number;
  imageHeight: number;
  vignetteParams: VignetteParams;
  onVignetteParamChange: (path: string[], value: number) => void;
}

export function BeforeAfter({
  originalUrl,
  images,
  selectedStep,
  vignetteOverlayEnabled,
  faceOvalOverlayEnabled,
  faceOval,
  onFaceOvalChange,
  imageWidth,
  imageHeight,
  vignetteParams,
  onVignetteParamChange,
}: Props) {
  const stepLabel = STEP_LABELS[selectedStep] ?? selectedStep;

  const showVignette =
    vignetteOverlayEnabled &&
    selectedStep === "final" &&
    imageWidth > 0 &&
    imageHeight > 0;

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
        vignetteOverlayEnabled={showVignette}
        faceOvalOverlayEnabled={showFaceOval}
        faceOval={faceOval}
        onFaceOvalChange={onFaceOvalChange}
        imageWidth={imageWidth}
        imageHeight={imageHeight}
        vignetteParams={vignetteParams}
        onVignetteParamChange={onVignetteParamChange}
      />
    </div>
  );
}
