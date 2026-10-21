import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";

export function useAuthMode() {
  return useQuery({
    queryKey: ["auth-config"],
    queryFn: async ({ signal }) =>
      (await api.GET("/api/v1/auth/config", { signal })).data!,
    staleTime: 60_000,
    retry: false,
  });
}
export function PublicDemoNotice() {
  const mode = useAuthMode();
  return mode.data?.public_demo_only ? (
    <aside className="demo-banner" aria-label="Public demo notice">
      <strong>
        Public demo — do not upload real statements or personal data
      </strong>
      <p>
        Isolated disposable demo session. Synthetic data only; file uploads are
        disabled. Reloading signs you out. Accounts expire within 24 hours;
        purge runs while the free service is awake.
      </p>
    </aside>
  ) : null;
}
