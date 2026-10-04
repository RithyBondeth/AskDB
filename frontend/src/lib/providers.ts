// Display details for each model provider. The backend decides which models each
// one offers (GET /api/models); this file is only about how they look and where
// to get a key.
import { Bot, Cpu, Gift, type LucideIcon, Network, Sparkles, Zap } from "lucide-react";

import type { ModelsResponse, Provider } from "@/lib/types";

export interface ProviderInfo {
  id: Provider;
  /** Name in menus. */
  label: string;
  icon: LucideIcon;
  /** One line under the name in the key dialog. */
  blurb: string;
  /** Where to create a key (absent for the local model). */
  key?: { url: string; site: string; placeholder: string; free: boolean };
}

export const PROVIDERS: ProviderInfo[] = [
  {
    id: "free",
    label: "Free (Gemini)",
    icon: Gift,
    blurb: "Google Gemini's free tier",
    key: {
      url: "https://aistudio.google.com/apikey",
      site: "aistudio.google.com/apikey",
      placeholder: "AIza…",
      free: true,
    },
  },
  {
    id: "claude",
    label: "Claude",
    icon: Bot,
    blurb: "Anthropic: Opus, Sonnet, Haiku and Fable",
    key: {
      url: "https://platform.claude.com/",
      site: "platform.claude.com",
      placeholder: "sk-ant-…",
      free: false,
    },
  },
  {
    id: "groq",
    label: "Groq",
    icon: Zap,
    blurb: "Fast open models, with a free tier",
    key: {
      url: "https://console.groq.com/keys",
      site: "console.groq.com/keys",
      placeholder: "gsk_…",
      free: true,
    },
  },
  {
    id: "openrouter",
    label: "OpenRouter",
    icon: Network,
    blurb: "Hundreds of models behind one key, some free",
    key: {
      url: "https://openrouter.ai/settings/keys",
      site: "openrouter.ai/settings/keys",
      placeholder: "sk-or-…",
      free: true,
    },
  },
  {
    id: "openai",
    label: "OpenAI",
    icon: Sparkles,
    blurb: "GPT models",
    key: {
      url: "https://platform.openai.com/api-keys",
      site: "platform.openai.com/api-keys",
      placeholder: "sk-…",
      free: false,
    },
  },
  {
    id: "local",
    label: "Open model (local)",
    icon: Cpu,
    blurb: "Runs on your machine with Ollama",
  },
];

export const PROVIDER_IDS = PROVIDERS.map((p) => p.id);

export function providerInfo(id: Provider): ProviderInfo {
  return PROVIDERS.find((p) => p.id === id) ?? PROVIDERS[0];
}

export function isProvider(value: unknown): value is Provider {
  return typeof value === "string" && (PROVIDER_IDS as string[]).includes(value);
}

/** The model to ask with: the user's pick if the provider still offers it,
 *  otherwise the provider's default. */
export function effectiveModel(
  choice: string | undefined,
  list: ModelsResponse | undefined,
  fallback: string | undefined,
): string | undefined {
  if (!list) return choice ?? fallback;
  if (choice && list.models.some((m) => m.id === choice)) return choice;
  return list.default;
}

/** A short name for a model id: "hf.co/org/Model-GGUF:Q4" → "Model-GGUF:Q4". */
export function shortModel(id: string): string {
  return id.split("/").at(-1) ?? id;
}
