import axios, {
  AxiosError,
  AxiosHeaders,
  type AxiosAdapter,
  type AxiosResponse,
  type InternalAxiosRequestConfig,
} from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getAccessToken, getRefreshToken, setTokens } from '../../lib/tokenStorage';
import api, { AUTH_EXPIRED_EVENT } from '../../services/api';

function respond(
  config: InternalAxiosRequestConfig,
  status: number,
  data: unknown,
): Promise<AxiosResponse> {
  const response: AxiosResponse = { data, status, statusText: String(status), headers: {}, config };
  if (status >= 400) {
    return Promise.reject(
      new AxiosError(`Request failed with status ${status}`, AxiosError.ERR_BAD_REQUEST, config, null, response),
    );
  }
  return Promise.resolve(response);
}

function authHeader(config: InternalAxiosRequestConfig): string | undefined {
  const value = AxiosHeaders.from(config.headers).get('Authorization');
  return typeof value === 'string' ? value : undefined;
}

const NEW_PAIR = { access_token: 'new-access', refresh_token: 'new-refresh', token_type: 'bearer' };

describe('api 401 refresh interceptor', () => {
  const originalAdapter = api.defaults.adapter;

  beforeEach(() => {
    window.localStorage.clear();
    setTokens('old-access', 'old-refresh');
  });

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    vi.restoreAllMocks();
  });

  it('refreshes once and retries the original request with the new token', async () => {
    const adapter = vi.fn<AxiosAdapter>((config) =>
      authHeader(config) === 'Bearer new-access'
        ? respond(config, 200, { ok: true })
        : respond(config, 401, { detail: 'expired' }),
    );
    api.defaults.adapter = adapter;
    const post = vi.spyOn(axios, 'post').mockResolvedValue({ data: NEW_PAIR });

    const res = await api.get('/roasts/mine');

    expect(res.data).toEqual({ ok: true });
    expect(post).toHaveBeenCalledTimes(1);
    expect(post.mock.calls[0][1]).toEqual({ refresh_token: 'old-refresh' });
    expect(adapter).toHaveBeenCalledTimes(2);
    expect(getAccessToken()).toBe('new-access');
    expect(getRefreshToken()).toBe('new-refresh');
  });

  it('shares one refresh across concurrent 401s', async () => {
    api.defaults.adapter = (config) =>
      authHeader(config) === 'Bearer new-access'
        ? respond(config, 200, { url: config.url })
        : respond(config, 401, { detail: 'expired' });
    const post = vi.spyOn(axios, 'post').mockResolvedValue({ data: NEW_PAIR });

    const [a, b] = await Promise.all([api.get('/a'), api.get('/b')]);

    expect(a.data).toEqual({ url: '/a' });
    expect(b.data).toEqual({ url: '/b' });
    expect(post).toHaveBeenCalledTimes(1);
  });

  it('does not loop: a retried request that 401s again is rejected', async () => {
    const adapter = vi.fn<AxiosAdapter>((config) => respond(config, 401, { detail: 'nope' }));
    api.defaults.adapter = adapter;
    const post = vi.spyOn(axios, 'post').mockResolvedValue({ data: NEW_PAIR });

    await expect(api.get('/x')).rejects.toBeInstanceOf(AxiosError);
    expect(post).toHaveBeenCalledTimes(1);
    expect(adapter).toHaveBeenCalledTimes(2);
  });

  it('clears tokens and fires auth-expired when the refresh token is rejected (401)', async () => {
    api.defaults.adapter = (config) => respond(config, 401, { detail: 'expired' });
    vi.spyOn(axios, 'post').mockImplementation((url: string) =>
      respond({ url, headers: new AxiosHeaders() }, 401, { detail: 'Refresh token reused' }),
    );
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);

    await expect(api.get('/x')).rejects.toBeInstanceOf(AxiosError);

    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
    expect(listener).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('keeps the session when refresh fails transiently (5xx / network)', async () => {
    api.defaults.adapter = (config) => respond(config, 401, { detail: 'expired' });
    vi.spyOn(axios, 'post').mockRejectedValue(new Error('Network Error'));
    const listener = vi.fn();
    window.addEventListener(AUTH_EXPIRED_EVENT, listener);

    await expect(api.get('/x')).rejects.toBeInstanceOf(AxiosError);

    window.removeEventListener(AUTH_EXPIRED_EVENT, listener);
    expect(listener).not.toHaveBeenCalled();
    expect(getRefreshToken()).toBe('old-refresh');
  });

  it('reuses a pair another tab already rotated instead of replaying the old token', async () => {
    let calls = 0;
    api.defaults.adapter = (config) => {
      calls += 1;
      // First call fails with the stale token; meanwhile "another tab" rotated the pair.
      if (calls === 1) {
        setTokens('other-tab-access', 'other-tab-refresh');
        return respond(config, 401, { detail: 'expired' });
      }
      return respond(config, 200, { auth: authHeader(config) });
    };
    const post = vi.spyOn(axios, 'post');

    const res = await api.get<{ auth: string }>('/x');

    expect(post).not.toHaveBeenCalled();
    expect(res.data.auth).toBe('Bearer other-tab-access');
  });

  it('never refreshes for /auth/logout 401s', async () => {
    api.defaults.adapter = (config) => respond(config, 401, { detail: 'bad' });
    const post = vi.spyOn(axios, 'post');

    await expect(api.post('/auth/logout', { refresh_token: 'x' })).rejects.toBeInstanceOf(AxiosError);
    expect(post).not.toHaveBeenCalled();
  });
});
