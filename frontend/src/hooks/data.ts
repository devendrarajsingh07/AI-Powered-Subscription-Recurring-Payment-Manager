import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "../api/client";
import type { operations } from "../api/schema";

export type SubscriptionFilters = NonNullable<
  operations["subscriptions_api_v1_subscriptions_get"]["parameters"]["query"]
>;
export const useSummary = () =>
  useQuery({
    queryKey: ["summary"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/summary", { signal })).data!,
  });
export const useTrend = () =>
  useQuery({
    queryKey: ["trend"],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/summary/trend", {
          signal,
          params: { query: { months: 12 } },
        })
      ).data!,
  });
export const useRenewals = (limit = 100, offset = 0) =>
  useQuery({
    queryKey: ["renewals", limit, offset],
    queryFn: async ({ signal }) =>
      (
        await api.GET("/api/v1/renewals/upcoming", {
          signal,
          params: { query: { days: 30, limit, offset } },
        })
      ).data!,
  });
export const useSubscriptions = (query: SubscriptionFilters) =>
  useQuery({
    queryKey: ["subscriptions", query],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/subscriptions", { signal, params: { query } }))
        .data!,
  });
export function useRefresh() {
  const client = useQueryClient();
  return useCallback(async () => {
    await Promise.all(
      [
        "subscriptions",
        "subscription",
        "summary",
        "trend",
        "renewals",
        "categories",
        "uploads",
        "recommendations",
        "savings",
        "alerts",
      ].map((key) => client.invalidateQueries({ queryKey: [key] })),
    );
  }, [client]);
}
