// A random id for this browser. Databases you upload belong to it, so other people
// using the same AskDB server can't see or delete them. It isn't an account:
// clearing site data (or another browser) means a new id and no access to old uploads.
const STORAGE_KEY = "askdb:owner";
export const OWNER_HEADER = "x-askdb-owner";

let fallback: string | undefined; // storage blocked: the id lasts until the tab closes

export function ownerId(): string {
  try {
    let id = localStorage.getItem(STORAGE_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(STORAGE_KEY, id);
    }
    return id;
  } catch {
    fallback ??= crypto.randomUUID();
    return fallback;
  }
}

/** Headers for a request to our /api routes, including this browser's id. */
export function ownerHeaders(headers: Record<string, string> = {}): Record<string, string> {
  return { ...headers, [OWNER_HEADER]: ownerId() };
}
