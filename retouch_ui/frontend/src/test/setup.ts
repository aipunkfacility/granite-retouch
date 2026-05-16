import '@testing-library/jest-dom';
import { vi } from 'vitest';
if (typeof PointerEvent !== 'undefined') {
  PointerEvent.prototype.getModifierState = vi.fn().mockReturnValue(false);
}
// ResizeObserver mock for useRenderMetrics hook
class ResizeObserverMock {
  observe = vi.fn();
  unobserve = vi.fn();
  disconnect = vi.fn();
}
if (typeof ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = ResizeObserverMock as unknown as typeof ResizeObserver;
}
