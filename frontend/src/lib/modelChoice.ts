// The provider and per-provider model this browser last picked, so the menu
// remembers them across visits. Stored in localStorage only.
import { isProvider } from "@/lib/providers";
import type { Provider } from "@/lib/types";

const STORAGE_KEY = "askdb:model-choice";

export interface ModelChoice {
  provider?: Provider;
  /** Last model picked for each provider. */
  models: Partial<Record<Provider, string>>;
}

export function loadChoice(): ModelChoice {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    const models: ModelChoice["models"] = {};
    for (const [p, m] of Object.entries(raw.models ?? {})) {
      if (isProvider(p) && typeof m === "string" && m) models[p] = m;
    }
    return { provider: isProvider(raw.provider) ? raw.provider : undefined, models };
  } catch {
    return { models: {} };
  }
}

export function saveChoice(choice: ModelChoice) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(choice));
  } catch {
    // Storage blocked: the choice lasts until the tab closes.
  }
}
