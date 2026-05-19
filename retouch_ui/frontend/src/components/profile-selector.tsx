import type { ProfileType } from "../lib/types";

interface Props {
  profile: ProfileType;
  onChange: (profile: ProfileType) => void;
  disabled?: boolean;
}

const PROFILES: { value: ProfileType; label: string; desc: string }[] = [
  { value: "preserve", label: "Preserve", desc: "Максимальная сохранность, минимум изменений" },
  { value: "standard", label: "Standard", desc: "Сбалансированный профиль (по умолчанию)" },
  { value: "diagnostic", label: "Diagnostic", desc: "Все проверки и гейты активны" },
];

export function ProfileSelector({ profile, onChange, disabled }: Props) {
  return (
    <div className="flex items-center gap-2">
      <label className="text-xs text-text-secondary font-medium whitespace-nowrap">
        Profile
      </label>
      <div className="flex rounded-lg border border-border overflow-hidden">
        {PROFILES.map((p) => (
          <button
            key={p.value}
            onClick={() => onChange(p.value)}
            disabled={disabled}
            title={p.desc}
            className={`px-2.5 py-1 text-xs font-medium transition-colors duration-150
              ${profile === p.value
                ? "bg-accent-blue text-white"
                : "bg-bg-card text-text-secondary hover:bg-bg-hover hover:text-text-primary"
              }
              disabled:opacity-50 disabled:cursor-not-allowed
              border-r border-border last:border-r-0`}
          >
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}
