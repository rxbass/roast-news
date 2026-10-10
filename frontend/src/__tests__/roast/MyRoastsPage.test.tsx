import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { MyRoastsPage } from '../../pages/MyRoastsPage';
import { deleteRoast, getMyRoasts } from '../../services/roastService';
import { renderWithProviders } from '../test-utils';
import { makeAxiosError, makeRoast } from './fixtures';

vi.mock('../../services/roastService', () => ({
  MY_ROASTS_PAGE_SIZE: 10,
  createRoast: vi.fn(),
  getRoast: vi.fn(),
  getMyRoasts: vi.fn(),
  deleteRoast: vi.fn(),
}));

const getMyRoastsMock = vi.mocked(getMyRoasts);
const deleteRoastMock = vi.mocked(deleteRoast);

describe('MyRoastsPage', () => {
  beforeEach(() => {
    getMyRoastsMock.mockReset();
    deleteRoastMock.mockReset();
  });

  it('shows the empty state with a CTA', async () => {
    getMyRoastsMock.mockResolvedValue({ items: [], total: 0, page: 1, size: 10 });
    renderWithProviders(<MyRoastsPage />, ['/my-roasts']);

    expect(await screen.findByTestId('my-roasts-empty')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /roast something/i })).toBeInTheDocument();
    expect(getMyRoastsMock).toHaveBeenCalledWith(1, 10);
  });

  it('lists roasts and deletes one after confirmation', async () => {
    const user = userEvent.setup();
    const roast = makeRoast();
    getMyRoastsMock.mockResolvedValue({ items: [roast], total: 1, page: 1, size: 10 });
    deleteRoastMock.mockResolvedValue(undefined);
    renderWithProviders(<MyRoastsPage />, ['/my-roasts']);

    const item = await screen.findByTestId('roast-list-item');
    expect(within(item).getByRole('link', { name: /flyover/i })).toHaveAttribute(
      'href',
      `/roast/${roast.id}`,
    );

    await user.click(within(item).getByRole('button', { name: /delete roast/i }));
    const dialog = await screen.findByRole('alertdialog');
    await user.click(within(dialog).getByRole('button', { name: /^delete$/i }));

    await waitFor(() => expect(deleteRoastMock).toHaveBeenCalled());
    expect(deleteRoastMock.mock.calls[0][0]).toBe(roast.id);
    await waitFor(() => expect(getMyRoastsMock.mock.calls.length).toBeGreaterThan(1));
  });

  it('handles 401 gracefully', async () => {
    getMyRoastsMock.mockRejectedValue(makeAxiosError(401, { detail: 'Not authenticated' }));
    renderWithProviders(<MyRoastsPage />, ['/my-roasts']);

    expect(await screen.findByText(/sign in again/i)).toBeInTheDocument();
  });
});
