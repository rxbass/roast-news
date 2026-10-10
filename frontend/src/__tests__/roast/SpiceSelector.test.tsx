import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it, vi } from 'vitest';

import { SpiceSelector } from '../../components/roast/SpiceSelector';
import type { SpiceLevel } from '../../types/roast';
import { renderWithProviders } from '../test-utils';

function Harness({ onChange }: { onChange: (v: SpiceLevel) => void }) {
  const [value, setValue] = useState<SpiceLevel>('medium');
  return (
    <SpiceSelector
      value={value}
      onChange={(v) => {
        setValue(v);
        onChange(v);
      }}
    />
  );
}

describe('SpiceSelector', () => {
  it('renders three radios with medium selected by default', () => {
    renderWithProviders(<Harness onChange={vi.fn()} />);
    const radios = screen.getAllByRole('radio');
    expect(radios).toHaveLength(3);
    expect(screen.getByRole('radio', { name: /medium/i })).toBeChecked();
    expect(screen.getByRole('radio', { name: /mild/i })).not.toBeChecked();
  });

  it('selects a level on click', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<Harness onChange={onChange} />);

    await user.click(screen.getByText('Extra Spicy'));

    expect(onChange).toHaveBeenLastCalledWith('extra_spicy');
    expect(screen.getByRole('radio', { name: /extra spicy/i })).toBeChecked();
  });

  it('is keyboard navigable with arrow keys', async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(<Harness onChange={onChange} />);

    const medium = screen.getByRole('radio', { name: /medium/i });
    medium.focus();
    expect(medium).toHaveFocus();

    await user.keyboard('{ArrowRight}');
    expect(onChange).toHaveBeenLastCalledWith('extra_spicy');
    expect(screen.getByRole('radio', { name: /extra spicy/i })).toBeChecked();

    await user.keyboard('{ArrowLeft}{ArrowLeft}');
    expect(onChange).toHaveBeenLastCalledWith('mild');
    expect(screen.getByRole('radio', { name: /mild/i })).toBeChecked();
  });
});
