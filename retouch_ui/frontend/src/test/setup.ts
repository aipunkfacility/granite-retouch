import '@testing-library/jest-dom';
import { vi } from 'vitest';
if (typeof PointerEvent !== 'undefined') {
  PointerEvent.prototype.getModifierState = vi.fn().mockReturnValue(false);
}
