import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { RoastPage } from '../../pages/RoastPage';
import { getRoast } from '../../services/roastService';
import { renderWithProviders } from '../test-utils';
import { makeAxiosError, makeRoast } from './fixtures';

vi.mock('../../services/roastService', () => ({
  MY_ROASTS_PAGE_SIZE: 10,
  createRoast: vi.fn(),
  getRoast: vi.fn(),
  getMyRoasts: vi.fn(),
  deleteRoast: vi.fn(),
}));

const getRoastMock = vi.mocked(getRoast);

function renderAt(id: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/roast/:id" element={<RoastPage />} />
    </Routes>,
    [`/roast/${id}`],
  );
}

describe('RoastPage', () => {
  beforeEach(() => {
    getRoastMock.mockReset();
  });

  it('shows the friendly 404 state', async () => {
    getRoastMock.mockRejectedValue(makeAxiosError(404, { detail: 'Roast not found' }));
    renderAt('missing-id');

    expect(await screen.findByText(/thedi thedi paathen, kaanom/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /roast your own/i })).toBeInTheDocument();
    expect(getRoastMock).toHaveBeenCalledTimes(1);
    expect(getRoastMock).toHaveBeenCalledWith('missing-id');
  });

  it('renders a completed roast and sets the document title', async () => {
    const roast = makeRoast();
    getRoastMock.mockResolvedValue(roast);
    renderAt(roast.id);

    expect(await screen.findByTestId('roast-card')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /roast your own news/i })).toBeInTheDocument();
    expect(document.title).toContain(roast.article_title);
  });

  it('shows the message for a refused roast', async () => {
    getRoastMock.mockResolvedValue(
      makeRoast({ status: 'refused', roast_text: null, message: 'Indha topic-ku roast illa machan' }),
    );
    renderAt('refused-id');

    expect(await screen.findByText('Indha topic-ku roast illa machan')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /whatsapp/i })).toBeNull();
  });
});
