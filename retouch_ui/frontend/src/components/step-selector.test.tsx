import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StepSelector } from './step-selector';
import { vi } from 'vitest';

// ─── FIX-6: StepSelector without machineType prop ───
describe('StepSelector (FIX-6)', () => {
  const defaultProps = {
    selectedStep: 'final',
    onStepChange: vi.fn(),
    availableSteps: ['chromakey', 'glow', 'final'],
  };

  it('renders without machineType prop', () => {
    // FIX-6: machineType was removed from Props — this should work fine
    expect(() => render(<StepSelector {...defaultProps} />)).not.toThrow();
  });

  it('shows dither button when onRequestDitherPreview is provided', () => {
    render(
      <StepSelector
        {...defaultProps}
        exportMode="1bit"
        onRequestDitherPreview={vi.fn()}
      />,
    );
    // The button should exist
    const ditherButton = screen.getByTitle(/Предпросмотр дизеринга/i);
    expect(ditherButton).toBeInTheDocument();
  });

  it('dither button title changes based on exportMode', () => {
    const { rerender } = render(
      <StepSelector
        {...defaultProps}
        exportMode="1bit"
        onRequestDitherPreview={vi.fn()}
      />,
    );
    expect(screen.getByTitle(/может быть медленно/i)).toBeInTheDocument();

    rerender(
      <StepSelector
        {...defaultProps}
        exportMode="8bit"
        onRequestDitherPreview={vi.fn()}
      />,
    );
    expect(screen.getByTitle(/Переключите экспорт/i)).toBeInTheDocument();
  });
});
