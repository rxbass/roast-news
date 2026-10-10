import type { Roast, RoastCreate, RoastList } from '../types/roast';
import api from './api';

/** Page size used by the "My Roasts" history. */
export const MY_ROASTS_PAGE_SIZE = 10;

/** POST /roasts -> 201 (new) or 200 (cached, `cached: true`). */
export async function createRoast(payload: RoastCreate): Promise<Roast> {
  // Scrape + moderation + generation can take a while, but never hang forever.
  const { data } = await api.post<Roast>('/roasts', payload, { timeout: 60_000 });
  return data;
}

/** GET /roasts/{id} -> Roast (404 if missing). */
export async function getRoast(id: string): Promise<Roast> {
  const { data } = await api.get<Roast>(`/roasts/${encodeURIComponent(id)}`);
  return data;
}

/** GET /roasts/me?page=&size= -> paginated history of the signed-in user. */
export async function getMyRoasts(page: number, size: number = MY_ROASTS_PAGE_SIZE): Promise<RoastList> {
  const { data } = await api.get<RoastList>('/roasts/me', { params: { page, size } });
  return data;
}

/** DELETE /roasts/{id} -> 204 (owner only). */
export async function deleteRoast(id: string): Promise<void> {
  await api.delete(`/roasts/${encodeURIComponent(id)}`);
}

export const roastService = { createRoast, getRoast, getMyRoasts, deleteRoast };

export default roastService;
