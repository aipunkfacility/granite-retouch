/** Side-by-side before/after preview with step labels */

interface Props {
  originalUrl: string | null;
  images: Record<string, string>;
  selectedStep: string;
  onStepChange: (step: string) => void;
}

const STEPS = [
  { key: "chromakey", label: "Хромакей" },
  { key: "glow", label: "Glow" },
  { key: "leveled", label: "Levels" },
  { key: "face_corrected", label: "Лицо" },
  { key: "final", label: "Результат" },
];

export function BeforeAfter({ originalUrl, images, selectedStep }: Props) {
  const stepLabel = STEPS.find((s) => s.key === selectedStep)?.label ?? selectedStep;

  return (
    <div className="flex gap-4 w-full">
      {/* Before */}
      <div className="flex-1 flex flex-col">
        <p className="text-text-secondary text-sm mb-1 font-heading font-semibold">До</p>
        <div className="bg-bg-secondary rounded-lg overflow-hidden flex items-center justify-center min-h-[200px]">
          {originalUrl ? (
            <img src={originalUrl} alt="Original" className="max-h-[500px] object-contain" />
          ) : (
            <span className="text-text-muted text-sm">Нет изображения</span>
          )}
        </div>
      </div>
      {/* After */}
      <div className="flex-1 flex flex-col">
        <p className="text-text-secondary text-sm mb-1 font-heading font-semibold">
          После: {stepLabel}
        </p>
        <div className="bg-bg-secondary rounded-lg overflow-hidden flex items-center justify-center min-h-[200px]">
          {images[selectedStep] ? (
            <img src={images[selectedStep]} alt={`Step: ${stepLabel}`} className="max-h-[500px] object-contain" />
          ) : (
            <span className="text-text-muted text-sm">Нет данных</span>
          )}
        </div>
      </div>
    </div>
  );
}
