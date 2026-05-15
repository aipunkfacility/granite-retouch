import { useId } from "react";

interface SliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  overridden?: boolean;
  onChange: (value: number) => void;
  onReset?: () => void;
}

/**
 * Custom Slider with track fill visualisation and optional reset icon.
 * Replaces bare <input type="range"> for consistent dark-theme appearance.
 */
export function Slider({
  label,
  value,
  min,
  max,
  step,
  unit,
  overridden = false,
  onChange,
  onReset,
}: SliderProps) {
  const id = useId();
  const pct = ((value - min) / (max - min)) * 100;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm items-center">
        <label
          htmlFor={id}
          className={`text-text-secondary ${overridden ? "font-semibold text-accent-orange" : ""}`}
        >
          {label}
        </label>
        <div className="flex items-center gap-1">
          <span className="text-text-muted font-mono text-xs">
            {value}
            {unit ? ` ${unit}` : ""}
          </span>
          {overridden && onReset && (
            <button
              onClick={onReset}
              className="text-xs text-accent-orange hover:text-accent-orange/80 transition-colors"
              title="Сбросить к значению пресета"
              aria-label={`Сбросить ${label}`}
            >
              <i className="ri-arrow-go-back-line" />
            </button>
          )}
        </div>
      </div>
      <div className="relative">
        {/* Track fill */}
        <div
          className="slider-fill absolute left-0 top-1/2 -translate-y-1/2 h-1 rounded-full bg-accent-blue pointer-events-none"
          style={{ width: `${pct}%` }}
        />
        <input
          id={id}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(parseFloat(e.target.value))}
          aria-valuemin={min}
          aria-valuemax={max}
          aria-valuenow={value}
          aria-label={label}
          role="slider"
          className="w-full relative z-10"
        />
      </div>
    </div>
  );
}
