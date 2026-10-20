import { task } from "@trigger.dev/sdk";
export const normalizeLead = task({
  id: "normalize-lead",
  maxDuration: 60,
  run: async (payload: { email?: string }) => ({ email: payload.email?.toLowerCase() }),
});
