import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { RoastCard } from '../../components/roast/RoastCard';
import { renderWithProviders } from '../test-utils';
import { makeRoast } from './fixtures';

describe('RoastCard', () => {
  it('renders roast text as plain text, never as HTML', () => {
    const malicious = '<script>alert("xss")</script>\n<b>bold</b> line two';
    const { container } = renderWithProviders(<RoastCard roast={makeRoast({ roast_text: malicious })} />);

    const text = screen.getByTestId('roast-text');
    expect(text.textContent).toBe(malicious);
    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('b')).toBeNull();
  });

  it('shows the movie title, year, language and poster', () => {
    renderWithProviders(<RoastCard roast={makeRoast()} />);
    expect(screen.getByRole('heading', { name: 'Thunder Raja (2019)' })).toBeInTheDocument();
    expect(screen.getByText('Tamil')).toBeInTheDocument();
    expect(screen.getByAltText('Thunder Raja poster')).toHaveAttribute(
      'src',
      'https://image.tmdb.org/t/p/w342/thunder.jpg',
    );
  });

  it('shows the reaction GIF with GIPHY attribution', () => {
    renderWithProviders(<RoastCard roast={makeRoast()} />);
    expect(screen.getByAltText('Reaction GIF')).toHaveAttribute(
      'src',
      'https://media1.giphy.com/media/abc123/200.gif',
    );
    const credit = screen.getByRole('link', { name: /powered by giphy/i });
    expect(credit).toHaveAttribute('href', 'https://giphy.com/gifs/facepalm-abc123');
    expect(credit.getAttribute('rel')).toContain('noopener');
  });

  it('hides the GIF when the roast has none, or when it fails to load', () => {
    const { unmount } = renderWithProviders(<RoastCard roast={makeRoast({ gif: null })} />);
    expect(screen.queryByTestId('roast-gif')).toBeNull();
    unmount();

    renderWithProviders(<RoastCard roast={makeRoast()} />);
    fireEvent.error(screen.getByAltText('Reaction GIF'));
    expect(screen.queryByTestId('roast-gif')).toBeNull();
  });

  it('falls back to a clapperboard when the poster fails to load', () => {
    renderWithProviders(<RoastCard roast={makeRoast()} />);
    fireEvent.error(screen.getByAltText('Thunder Raja poster'));
    expect(screen.getByTestId('poster-fallback')).toBeInTheDocument();
  });

  it('shows share buttons for a completed roast', () => {
    renderWithProviders(<RoastCard roast={makeRoast()} />);
    expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument();
    const wa = screen.getByRole('link', { name: /whatsapp/i });
    expect(wa.getAttribute('href')).toMatch(/^https:\/\/wa\.me\/\?text=/);
    expect(wa).toHaveAttribute('rel', 'noopener noreferrer');
    const x = screen.getByRole('link', { name: /share on x/i });
    expect(x.getAttribute('href')).toMatch(/^https:\/\/twitter\.com\/intent\/tweet\?text=/);
  });

  it('shows the cached badge for cached roasts', () => {
    renderWithProviders(<RoastCard roast={makeRoast({ cached: true })} />);
    expect(screen.getByText(/already roasted/i)).toBeInTheDocument();
  });

  it('shows the refusal message and no share buttons when refused', () => {
    const message = 'Indha padathai roast panna manasu varala machan 🙏';
    renderWithProviders(
      <RoastCard
        roast={makeRoast({ status: 'refused', roast_text: null, message, refusal_reason: 'sensitive_topic' })}
      />,
    );

    expect(screen.getByTestId('roast-refused')).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(screen.queryByTestId('roast-card')).toBeNull();
    expect(screen.queryByRole('button', { name: /copy/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /whatsapp/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /share on x/i })).toBeNull();
  });
});
