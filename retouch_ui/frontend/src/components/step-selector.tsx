/** Switcher for intermediate processing steps */

interface Props {
  selectedStep: string;
  onStepChange: (step: string) => void;
  availableSteps: string[];
  machineType?: string;
  onRequestDitherPreview?: () => void;
  ditherLoading?: boolean;
}

export const STEP_LABELS: Record<string, string> = {
  chromakey: "Хромакей",
  glow: "Glow",
  leveled: "Levels",
  face_corrected: "Лицо",
  final: "Результат",
  arch_mask: "Маска",
  dithered: "Dithered",
};

/** Define the canonical step order */
const STEP_ORDER = ["chromakey", "glow", "leveled", "face_corrected", "arch_mask", "final"];

export function StepSelector({ selectedStep, onStepChange, availableSteps, machineType, onRequestDitherPreview, ditherLoading }: Props) {
  const orderedSteps = STEP_ORDER.filter((s) => availableSteps.includes(s));
  // Include any steps not in the canonical order
  const extraSteps = availableSteps.filter((s) => !STEP_ORDER.includes(s));
  const allSteps = [...orderedSteps, ...extraSteps];

  return (
    <div className="flex gap-1 flex-wrap items-center">
      {allSteps.map((step) => (
        <button
          key={step}
          onClick={() => onStepChange(step)}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors
            ${
              step === selectedStep
                ? "bg-accent-blue text-white"
                : "bg-bg-card text-text-secondary hover:bg-bg-hover"
            }`}
        >
          {STEP_LABELS[step] || step}
        </button>
      ))}
      {/* Dither preview button — only for laser_80w */}
      {machineType === "laser_80w" && onRequestDitherPreview && (
        <button
          onClick={onRequestDitherPreview}
          disabled={ditherLoading}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors border border-dashed
            ${
              ditherLoading
                ? "border-accent-orange/50 text-accent-orange/60 cursor-wait"
                : "border-accent-orange/30 text-accent-orange hover:bg-accent-orange/10"
            }`}
          title="Предпросмотр Jarvis дизеринга (может быть медленно без Numba)"
        >
          {ditherLoading ? (
            <span className="flex items-center gap-1">
              <i className="ri-loader-4-line animate-spin" />
              Дизеринг...
            </span>
          ) : (
            <span className="flex items-center gap-1">
              <i className="ri-contrast-2-line" />
              Просмотр дизеринга
            </span>
          )}
        </button>
      )}
    </div>
  );
}
