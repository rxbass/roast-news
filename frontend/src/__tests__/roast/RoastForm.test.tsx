import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { RoastForm } from '../../components/roast/RoastForm';
import { renderWithProviders } from '../test-utils';

describe('RoastForm', () => {
  it('shows a validation error for an invalid URL and does not submit', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/news link/i), 'not a url');
    await user.click(screen.getByRole('button', { name: /roast pannu/i }));

    expect(await screen.findByText(/idhu url-ae illa/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects non-http(s) schemes', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/news link/i), 'ftp://example.com/file');
    await user.click(screen.getByRole('button', { name: /roast pannu/i }));

    expect(await screen.findByText(/only http/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects URLs longer than 2048 characters', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    const input = screen.getByLabelText(/news link/i);
    await user.click(input);
    await user.paste(`https://example.com/${'a'.repeat(2050)}`);
    await user.click(screen.getByRole('button', { name: /roast pannu/i }));

    expect(await screen.findByText(/at most 2048/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits the trimmed URL and the chosen spice level', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/news link/i), '  https://news.example.com/story  ');
    await user.click(screen.getByText('Extra Spicy'));
    await user.click(screen.getByRole('button', { name: /roast pannu/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({
      url: 'https://news.example.com/story',
      spice_level: 'extra_spicy',
    });
  });

  it('disables submit during a cooldown', () => {
    renderWithProviders(<RoastForm onSubmit={vi.fn()} cooldownSeconds={5} />);
    expect(screen.getByRole('button', { name: /wait 5s/i })).toBeDisabled();
  });
});
