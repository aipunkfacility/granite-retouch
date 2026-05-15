import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ToastProvider, useToast } from './toast-provider';

function TestConsumer({ message, options }: { message: string; options?: { type?: 'info' | 'error' | 'warning'; duration?: number } }) {
  const { showToast } = useToast();
  return (
    <button onClick={() => showToast(message, options)}>Show Toast</button>
  );
}

describe('ToastProvider', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders toast message', () => {
    render(
      <ToastProvider>
        <TestConsumer message="test message" />
      </ToastProvider>,
    );

    act(() => { screen.getByText('Show Toast').click(); });

    expect(screen.getByText('test message')).toBeTruthy();
  });

  it('auto-hides toast after duration', () => {
    render(
      <ToastProvider>
        <TestConsumer message="timed" options={{ duration: 100 }} />
      </ToastProvider>,
    );

    act(() => { screen.getByText('Show Toast').click(); });
    expect(screen.getByText('timed')).toBeTruthy();

    act(() => { vi.advanceTimersByTime(150); });
    expect(screen.queryByText('timed')).toBeNull();
  });

  it('new toast replaces previous', () => {
    function DualConsumer() {
      const { showToast } = useToast();
      return (
        <>
          <button onClick={() => showToast('first')}>First</button>
          <button onClick={() => showToast('second')}>Second</button>
        </>
      );
    }

    render(
      <ToastProvider>
        <DualConsumer />
      </ToastProvider>,
    );

    act(() => { screen.getByText('First').click(); });
    expect(screen.getByText('first')).toBeTruthy();

    act(() => { screen.getByText('Second').click(); });
    expect(screen.queryByText('first')).toBeNull();
    expect(screen.getByText('second')).toBeTruthy();
  });

  it('applies type CSS class', () => {
    const { container } = render(
      <ToastProvider>
        <TestConsumer message="err" options={{ type: 'error' }} />
      </ToastProvider>,
    );

    act(() => { screen.getByText('Show Toast').click(); });
    expect(container.querySelector('.toast-error')).toBeTruthy();
  });
});
