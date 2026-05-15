import { useCallback, useRef, useState } from "react";
import { uploadImage } from "../lib/api";

const ALLOWED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"];
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

interface Props {
  onImageUploaded: (fileId: string, previewUrl: string) => void;
}

export function ImageUpload({ onImageUploaded }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const validateFile = useCallback((file: File): string | null => {
    const ext = file.name.toLowerCase().slice(file.name.lastIndexOf("."));
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      return `Неподдерживаемый формат: ${ext}. Допустимы: ${ALLOWED_EXTENSIONS.join(", ")}`;
    }
    if (file.size > MAX_FILE_SIZE) {
      return `Файл слишком большой (${(file.size / 1024 / 1024).toFixed(1)} MB). Максимум: 50 MB`;
    }
    return null;
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        return;
      }

      setUploading(true);
      setError(null);
      try {
        const { file_id } = await uploadImage(file);
        const previewUrl = URL.createObjectURL(file);
        onImageUploaded(file_id, previewUrl);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        setError(msg);
      } finally {
        setUploading(false);
      }
    },
    [onImageUploaded, validateFile],
  );

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload image"
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer
        ${dragOver ? "border-accent-blue bg-bg-hover" : "border-border bg-bg-card"}`}
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          inputRef.current?.click();
        }
      }}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const file = e.dataTransfer.files[0];
        if (file) handleFile(file);
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) handleFile(file);
        }}
        className="hidden"
      />
      <div className="text-text-secondary">
        {uploading ? (
          <span className="text-accent-blue flex items-center justify-center gap-2">
            <i className="ri-loader-4-line animate-spin" />
            Загрузка...
          </span>
        ) : (
          <>
            <i className="ri-upload-cloud-2-line text-3xl block mb-2 text-text-muted" />
            <span>Перетащите PNG/TIFF или нажмите для выбора</span>
          </>
        )}
      </div>
      {error && <p className="text-accent-red mt-2 text-sm">{error}</p>}
    </div>
  );
}
