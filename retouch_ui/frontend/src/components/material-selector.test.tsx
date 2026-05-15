import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MaterialSelector } from './material-selector';
import { ToastProvider } from './toast-provider';
import type { MaterialType, MachineType, MaterialProfile, MaterialChange, ConfigTree } from '../lib/types';

function wrapWithToastProvider(ui: React.ReactElement) {
  return <ToastProvider>{ui}</ToastProvider>;
}

describe('MaterialSelector', () => {
  const mockOnSelect = vi.fn().mockResolvedValue({ success: true, validationWarnings: [] });

  const defaultProps = {
    material: 'granite' as MaterialType,
    machineType: 'laser_standard' as MachineType,
    profiles: {} as Record<string, MaterialProfile>,
    materialChanges: [] as MaterialChange[],
    validationWarnings: [] as string[],
    activeHint: null as string | null,
    onSelect: mockOnSelect,
    currentConfig: {} as ConfigTree,
  };

  beforeEach(() => {
    vi.useFakeTimers();
    mockOnSelect.mockClear();
    mockOnSelect.mockResolvedValue({ success: true, validationWarnings: [] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders without crashing', () => {
    render(wrapWithToastProvider(<MaterialSelector {...defaultProps} />));
    expect(screen.getByText('Материал')).toBeInTheDocument();
  });

  it('shows toast from useEffect when materialChanges arrive', () => {
    const changes: MaterialChange[] = [
      { param: 'gamma', old: 1.0, new: 1.2, reason: 'material adjust' },
    ];

    const { rerender } = render(wrapWithToastProvider(<MaterialSelector {...defaultProps} />));

    // Trigger materialChanges — should show toast via useEffect
    rerender(wrapWithToastProvider(<MaterialSelector {...defaultProps} materialChanges={changes} />));

    // After useEffect runs, toast should appear
    expect(screen.getByText(/gamma.*1.*1\.2/i)).toBeInTheDocument();
  });

  it('clears timeout on unmount', () => {
    const changes: MaterialChange[] = [
      { param: 'gamma', old: 1.0, new: 1.2 },
    ];

    const { unmount } = render(
      wrapWithToastProvider(<MaterialSelector {...defaultProps} materialChanges={changes} />),
    );

    // Toast should be visible
    expect(screen.getByText(/gamma/i)).toBeInTheDocument();

    // Unmount before timer fires — should not throw
    expect(() => unmount()).not.toThrow();

    // Advance timers — should not cause issues since cleanup ran
    act(() => { vi.advanceTimersByTime(6000); });
  });

  it('handles unsuccessful material selection with validationWarnings', async () => {
    mockOnSelect.mockResolvedValueOnce({
      success: false,
      validationWarnings: ['ERROR: Incompatible combination'],
    });

    render(wrapWithToastProvider(<MaterialSelector {...defaultProps} />));

    const marbleButton = screen.getByText('Мрамор');
    await act(async () => {
      marbleButton.click();
    });

    // Should show error toast
    await act(async () => {
      vi.advanceTimersByTime(0);
    });

    expect(screen.getByText(/Incompatible/i)).toBeInTheDocument();
  });

  // Dark palette: no light classes
  it('has no light palette classes (bg-yellow-50 etc)', () => {
    const { container } = render(wrapWithToastProvider(<MaterialSelector {...defaultProps} />));
    expect(container.querySelector('[class*="bg-yellow-50"]')).toBeNull();
    expect(container.querySelector('[class*="bg-amber-50"]')).toBeNull();
    expect(container.querySelector('[class*="bg-red-50"]')).toBeNull();
    expect(container.querySelector('[class*="bg-blue-50"]')).toBeNull();
  });

  // Emoji replaced with Remix Icon
  it('has no emoji characters', () => {
    render(wrapWithToastProvider(<MaterialSelector {...defaultProps} />));
    // Check for emoji by looking for common emoji that were replaced
    const { container } = render(wrapWithToastProvider(<MaterialSelector {...defaultProps} />));
    // No lightbulb emoji, warning emoji, forbidden emoji, info emoji as text
    expect(container.textContent).not.toContain('💡');
    expect(container.textContent).not.toContain('⚠️');
    expect(container.textContent).not.toContain('🚫');
    expect(container.textContent).not.toContain('ℹ️');
  });

  it('has Remix Icon for lightbulb hint', () => {
    const profiles = {
      granite: {
        step_mm_range: [0.1, 0.5],
        stone_gamma_range: [1.0, 2.0],
        hints: {},
      } as unknown as MaterialProfile,
    };
    const { container } = render(wrapWithToastProvider(<MaterialSelector {...defaultProps} material="granite" profiles={profiles} />));
    expect(container.querySelector('.ri-lightbulb-line')).toBeTruthy();
  });
});
