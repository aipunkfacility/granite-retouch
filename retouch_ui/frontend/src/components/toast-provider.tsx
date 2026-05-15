/* eslint-disable react-refresh/only-export-components */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ToastOptions {
  type?: 'info' | 'error' | 'warning';
  duration?: number; // ms
}

interface ToastEntry {
  message: string;
  type: Required<ToastOptions>['type'];
}

interface ToastContextValue {
  showToast: (message: string, options?: ToastOptions) => void;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const DEFAULT_TYPE: ToastOptions['type'] = 'info';
const DEFAULT_DURATION = 3000;

const TYPE_CLASSES: Record<Required<ToastOptions>['type'], string> = {
  info: 'bg-accent-blue/10 text-accent-blue border-accent-blue/30 toast-info',
  error: 'bg-accent-red/10 text-accent-red border-accent-red/30 toast-error',
  warning:
    'bg-accent-orange/10 text-accent-orange border-accent-orange/30 toast-warning',
};

const TYPE_ICONS: Record<Required<ToastOptions>['type'], string> = {
  info: 'ri-information-line',
  error: 'ri-forbid-line',
  warning: 'ri-alert-line',
};

/* ------------------------------------------------------------------ */
/*  Context                                                            */
/* ------------------------------------------------------------------ */

const ToastContext = createContext<ToastContextValue | null>(null);

/* ------------------------------------------------------------------ */
/*  Provider                                                           */
/* ------------------------------------------------------------------ */

export const ToastProvider: React.FC<React.PropsWithChildren> = ({
  children,
}) => {
  const [toast, setToast] = useState<ToastEntry | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const showToast = useCallback(
    (message: string, options?: ToastOptions) => {
      clearTimer();

      const type = options?.type ?? DEFAULT_TYPE;
      const duration = options?.duration ?? DEFAULT_DURATION;

      setToast({ message, type });

      timerRef.current = setTimeout(() => {
        setToast(null);
        timerRef.current = null;
      }, duration);
    },
    [clearTimer],
  );

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      clearTimer();
    };
  }, [clearTimer]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toast && (
        <div
          className={`fixed bottom-6 left-1/2 -translate-x-1/2 bg-bg-card border border-border text-text-primary px-5 py-3 rounded-lg shadow-lg z-50 text-sm max-w-md ${TYPE_CLASSES[toast.type]}`}
          role="alert"
        >
          <span className="flex items-center gap-2">
            <i className={`${TYPE_ICONS[toast.type]} text-base`} />
            <span>{toast.message}</span>
          </span>
        </div>
      )}
    </ToastContext.Provider>
  );
};

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export const useToast = (): ToastContextValue => {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error('useToast must be used within a <ToastProvider>');
  }
  return ctx;
};
