import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { HomePage } from '../../pages/HomePage';
import { searchMovies } from '../../services/movieService';
import { createRoast } from '../../services/roastService';
import { renderWithProviders } from '../test-utils';
import { makeAxiosError, makeMovieResult, makeRoast } from './fixtures';

vi.mock('../../services/roastService', () => ({
  MY_ROASTS_PAGE_SIZE: 10,
  createRoast: vi.fn(),
  getRoast: vi.fn(),
  getMyRoasts: vi.fn(),
  deleteRoast: vi.fn(),
}));

vi.mock('../../services/movieService', () => ({ searchMovies: vi.fn() }));

const createRoastMock = vi.mocked(createRoast);
const searchMock = vi.mocked(searchMovies);

async function pickMovieAndSubmit() {
  const user = userEvent.setup();
  await user.type(screen.getByRole('combobox', { name: /movie/i }), 'thunder');
  await user.click(await screen.findByRole('option', { name: /thunder raja/i }));
  await user.click(screen.getByRole('button', { name: /roast pannu/i }));
  return user;
}

describe('HomePage', () => {
  beforeEach(() => {
    createRoastMock.mockReset();
    searchMock.mockReset();
    searchMock.mockResolvedValue([makeMovieResult()]);
  });

  it('calls the create mutation with the correct payload and shows the roast', async () => {
    const roast = makeRoast();
    createRoastMock.mockResolvedValue(roast);
    renderWithProviders(<HomePage />);

    await pickMovieAndSubmit();

    await waitFor(() => expect(createRoastMock).toHaveBeenCalled());
    expect(createRoastMock.mock.calls[0][0]).toEqual({ tmdb_id: 4242, spice_level: 'medium' });
    expect(await screen.findByTestId('roast-card')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /permalink/i })).toHaveAttribute('href', `/roast/${roast.id}`);
  });

  it('shows a refused roast message without share buttons', async () => {
    createRoastMock.mockResolvedValue(
      makeRoast({ status: 'refused', roast_text: null, gif: null, message: 'Sensitive padam machan, skip pannren 🙏' }),
    );
    renderWithProviders(<HomePage />);

    await pickMovieAndSubmit();

    expect(await screen.findByText(/sensitive padam machan/i)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /whatsapp/i })).toBeNull();
  });

  it('shows the 400 error copy', async () => {
    createRoastMock.mockRejectedValue(makeAxiosError(400, { detail: 'Bad request' }));
    renderWithProviders(<HomePage />);

    await pickMovieAndSubmit();

    expect(await screen.findByText(/edho sari illa machan/i)).toBeInTheDocument();
  });

  it('prefers the server message when present', async () => {
    createRoastMock.mockRejectedValue(
      makeAxiosError(422, { detail: 'Too little info', message: 'Indha padathu pathi info kammi da!' }),
    );
    renderWithProviders(<HomePage />);

    await pickMovieAndSubmit();

    expect(await screen.findByText(/padathu info romba kammi/i)).toBeInTheDocument();
    expect(screen.getByText('Indha padathu pathi info kammi da!')).toBeInTheDocument();
  });

  it('shows a live Retry-After countdown on 429 and disables the button', async () => {
    createRoastMock.mockRejectedValue(
      makeAxiosError(429, { detail: 'Rate limit exceeded' }, { 'retry-after': '3' }),
    );
    renderWithProviders(<HomePage />);

    await pickMovieAndSubmit();

    expect(await screen.findByText(/konjam slow-a po machan/i)).toBeInTheDocument();
    expect(screen.getByTestId('cooldown')).toHaveTextContent('Try again in 3s');
    expect(screen.getByRole('button', { name: /wait 3s/i })).toBeDisabled();

    await waitFor(() => expect(screen.getByTestId('cooldown')).toHaveTextContent('Try again in 2s'), {
      timeout: 2500,
    });
  });
});
