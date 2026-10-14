"use client";

import { useQuery } from "@tanstack/react-query";
import { keys, type Api } from "@nflpi/shared";

/** A saved health answer cannot authorize passkey controls on a new screen. */
export function usePasskeysEnabled(api: Api): boolean {
  const health = useQuery({
    queryKey: keys.passkeyHealth,
    queryFn: () => api.health(),
    refetchOnMount: "always",
    retry: false,
  });
  return health.isSuccess && health.isFetchedAfterMount && !health.isFetching && health.data.passkeys === true;
}
