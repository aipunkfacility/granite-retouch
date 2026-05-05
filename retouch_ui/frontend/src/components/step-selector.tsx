/** Switcher for intermediate processing steps */

interface Props {
  selectedStep: string;
  onStepChange: (step: string) => void;
  availableSteps: string[];
}

const STEP_LABELS: Record<string, string> = {
  chromakey: "Хромакей",
  glow: "Glow",
  leveled: "Levels",
  face_corrected: "Лицо",
  final: "Результат",
  arch_mask: "Маска",
};

/** Define the canonical step order */
const STEP_ORDER = ["chromakey", "glow", "leveled", "face_corrected", "arch_mask", "final"];

export function StepSelector({ selectedStep, onStepChange, availableSteps }: Props) {
  const orderedSteps = STEP_ORDER.filter((s) => availableSteps.includes(s));
  // Include any steps not in the canonical order
  const extraSteps = availableSteps.filter((s) => !STEP_ORDER.includes(s));
  const allSteps = [...orderedSteps, ...extraSteps];

  return (
    <div className="flex gap-1 flex-wrap">
      {allSteps.map((step) => (
        <button
          key={step}
          onClick={() => onStepChange(step)}
          className={`px-3 py-1.5 text-sm rounded transition-colors
            ${
              step === selectedStep
                ? "bg-accent-blue text-white"
                : "bg-bg-card text-text-secondary hover:bg-bg-hover"
            }`}
        >
          {STEP_LABELS[step] || step}
        </button>
      ))}
    </div>
  );
}
