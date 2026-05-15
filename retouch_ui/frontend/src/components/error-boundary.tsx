import { Component, type ReactNode } from "react";

interface Props { children: ReactNode; fallback?: ReactNode; }
interface State { hasError: boolean; error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) { super(props); this.state = { hasError: false, error: null }; }
  static getDerivedStateFromError(error: Error): State { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 p-8">
          <div className="max-w-md text-center">
            <i className="ri-error-warning-line text-5xl text-red-400 mb-4 block" />
            <h2 className="text-lg font-semibold text-gray-900 mb-2">Что-то пошло не так</h2>
            <p className="text-sm text-gray-600 mb-4">{this.state.error?.message || "Неожиданная ошибка"}</p>
            <button onClick={() => { this.setState({ hasError: false, error: null }); window.location.reload(); }}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg text-sm hover:bg-blue-600">Перезагрузить</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
