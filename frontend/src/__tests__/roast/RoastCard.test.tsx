import { screen } from '@testing-library/react';
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

  it('links the article title to the source with safe rel attributes', () => {
    renderWithProviders(<RoastCard roast={makeRoast()} />);
    const link = screen.getByRole('link', { name: /flyover/i });
    expect(link).toHaveAttribute('href', 'https://news.example.com/story/123');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link.getAttribute('rel')).toContain('noopener');
    expect(link.getAttribute('rel')).toContain('noreferrer');
    expect(link.getAttribute('rel')).toContain('nofollow');
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
    const message = 'Indha news-a roast panna manasu varala machan 🙏';
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
