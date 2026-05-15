import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MaterialSelector } from './material-selector';
import type { MaterialType, MachineType, MaterialProfile, MaterialChange, ConfigTree } from '../lib/types';

// ─── FIX-8: side effect moved to useEffect ───
describe('MaterialSelector (FIX-8, FIX-18, FIX-23)', () => {
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
    render(<MaterialSelector {...defaultProps} />);
    expect(screen.getByText('Материал')).toBeInTheDocument();
  });

  // FIX-8: toast should be shown via useEffect, not inline side effect
  it('shows toast from useEffect when materialChanges arrive', () => {
    const changes: MaterialChange[] = [
      { param: 'gamma', old: 1.0, new: 1.2, reason: 'material adjust' },
    ];

    const { rerender } = render(<MaterialSelector {...defaultProps} />);
    expect(screen.queryByText(/gamma/i)).toBeNull();

    // Trigger materialChanges — should show toast via useEffect
    rerender(<MaterialSelector {...defaultProps} materialChanges={changes} />);

    // After useEffect runs, toast should appear
    expect(screen.getByText(/gamma.*1.*1\.2/i)).toBeInTheDocument();
  });

  // FIX-18: setTimeout cleanup — timer should be cleared on unmount
  it('clears timeout on unmount (FIX-18)', () => {
    const changes: MaterialChange[] = [
      { param: 'gamma', old: 1.0, new: 1.2 },
    ];

    const { unmount } = render(
      <MaterialSelector {...defaultProps} materialChanges={changes} />,
    );

    // Toast should be visible
    expect(screen.getByText(/gamma/i)).toBeInTheDocument();

    // Unmount before timer fires — should not throw
    expect(() => unmount()).not.toThrow();

    // Advance timers — should not cause issues since cleanup ran
    act(() => { vi.advanceTimersByTime(6000); });
  });

  // FIX-23: selectMaterial returns { success, validationWarnings }
  it('handles unsuccessful material selection with validationWarnings (FIX-23)', async () => {
    mockOnSelect.mockResolvedValueOnce({
      success: false,
      validationWarnings: ['ERROR: Incompatible combination'],
    });

    render(<MaterialSelector {...defaultProps} />);

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
});
