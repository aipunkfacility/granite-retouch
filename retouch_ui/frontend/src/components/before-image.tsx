/** Original image preview with dimension badge. Renders placeholder when no image. */

import { useState, type ReactNode } from "react";

interface Props {
  originalUrl: string | null;
}

export function BeforeImage({ originalUrl }: Props) {
  const [naturalSize, setNaturalSize] = useState<{ w: number; h: number } | null>(null);

  let content: ReactNode;

  if (originalUrl) {
    content = (
      <div className="relative inline-block">
        <img
          src={originalUrl}
          alt="Original"
          className="max-h-[min(70vh,600px)] object-contain"
          onLoad={(e) => {
            const img = e.currentTarget;
            setNaturalSize({ w: img.naturalWidth, h: img.naturalHeight });
          }}
        />
        {naturalSize && (
          <span className="absolute bottom-1 right-1 text-[10px] font-mono text-text-muted bg-black/50 px-1.5 py-0.5 rounded pointer-events-none select-none">
            {naturalSize.w} × {naturalSize.h}
          </span>
        )}
      </div>
    );
  } else {
    content = <span className="text-text-muted text-sm">Нет изображения</span>;
  }

  return (
    <div className="flex-1 flex flex-col">
      <h3 className="text-text-secondary text-sm mb-1 font-heading font-semibold">До</h3>
      <div className="bg-bg-secondary rounded-lg overflow-hidden flex items-center justify-center min-h-[200px]">
        {content}
      </div>
    </div>
  );
}
