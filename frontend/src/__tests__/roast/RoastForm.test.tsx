import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RoastForm } from '../../components/roast/RoastForm';
import { searchMovies } from '../../services/movieService';
import { renderWithProviders } from '../test-utils';
import { makeMovieResult } from './fixtures';

vi.mock('../../services/movieService', () => ({ searchMovies: vi.fn() }));

const searchMock = vi.mocked(searchMovies);

const LEO = makeMovieResult({ tmdb_id: 1, title: 'Leo', year: 2023, poster_url: null });
const JAILER = makeMovieResult({ tmdb_id: 2, title: 'Jailer', year: 2023, original_language: 'ta' });

describe('RoastForm', () => {
  beforeEach(() => {
    searchMock.mockReset();
    searchMock.mockResolvedValue([LEO, JAILER]);
  });

  it('asks for a movie before submitting', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole('button', { name: /roast pannu/i }));

    expect(await screen.findByText(/oru padam select pannu/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('searches, picks a movie by click and submits its id with the spice level', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    await user.type(screen.getByRole('combobox', { name: /movie/i }), 'jail');
    await waitFor(() => expect(searchMock).toHaveBeenCalledWith('jail', expect.anything()));
    await user.click(await screen.findByRole('option', { name: /jailer \(2023\)/i }));

    expect(screen.getByTestId('picked-movie')).toHaveTextContent('Jailer (2023)');
    await user.click(screen.getByText('Extra Spicy'));
    await user.click(screen.getByRole('button', { name: /roast pannu/i }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit).toHaveBeenCalledWith({ tmdb_id: 2, spice_level: 'extra_spicy' });
  });

  it('supports keyboard selection and changing the movie', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<RoastForm onSubmit={onSubmit} />);

    const input = screen.getByRole('combobox', { name: /movie/i });
    await user.type(input, 'le');
    await screen.findByRole('option', { name: /leo \(2023\)/i });
    // Two results: Down -> Jailer, Down wraps -> Leo, Up wraps -> Jailer, Up -> Leo.
    await user.keyboard('{ArrowDown}{ArrowDown}{ArrowUp}{ArrowUp}{Enter}');

    expect(screen.getByTestId('picked-movie')).toHaveTextContent('Leo (2023)');
    expect(screen.getByTestId('poster-fallback')).toBeInTheDocument(); // Leo has no poster here

    await user.click(screen.getByRole('button', { name: /change/i }));
    expect(screen.getByRole('combobox', { name: /movie/i })).toBeInTheDocument();
  });

  it('does not search for a single character', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoastForm onSubmit={vi.fn()} />);

    await user.type(screen.getByRole('combobox', { name: /movie/i }), 'x');
    await new Promise((r) => setTimeout(r, 400));
    expect(searchMock).not.toHaveBeenCalled();
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('shows a friendly message when nothing matches', async () => {
    searchMock.mockResolvedValue([]);
    const user = userEvent.setup();
    renderWithProviders(<RoastForm onSubmit={vi.fn()} />);

    await user.type(screen.getByRole('combobox', { name: /movie/i }), 'zzzz');
    expect(await screen.findByText(/padam kedaikala/i)).toBeInTheDocument();
  });

  it('shows an error line when search fails', async () => {
    searchMock.mockRejectedValue(new Error('down'));
    const user = userEvent.setup();
    renderWithProviders(<RoastForm onSubmit={vi.fn()} />);

    await user.type(screen.getByRole('combobox', { name: /movie/i }), 'leo');
    expect(await screen.findByText(/search velai seiyala/i)).toBeInTheDocument();
  });

  it('closes the results on Escape', async () => {
    const user = userEvent.setup();
    renderWithProviders(<RoastForm onSubmit={vi.fn()} />);

    await user.type(screen.getByRole('combobox', { name: /movie/i }), 'leo');
    await screen.findByRole('listbox');
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('disables submit during a cooldown', () => {
    renderWithProviders(<RoastForm onSubmit={vi.fn()} cooldownSeconds={5} />);
    expect(screen.getByRole('button', { name: /wait 5s/i })).toBeDisabled();
  });
});
