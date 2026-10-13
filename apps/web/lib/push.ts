import type { Api, PushSubscriptionIn, PushTestOut } from "@nflpi/shared";

export function testAlertWords(result: PushTestOut): { text: string; problem: boolean } {
  if (!result.configured || result.devices === 0) {
    return { text: "The server has no device to send to. Turn alerts off and on again.", problem: true };
  }
  const summary = result.delivered === result.devices
    ? `Delivered to ${result.delivered} ${result.delivered === 1 ? "device" : "devices"}.`
    : result.delivered === 0
      ? "Not delivered."
      : `Delivered to ${result.delivered} of ${result.devices} devices.`;
  const failures = result.results.filter((item) => !item.ok)
    .map((item) => ` ${item.host}: ${item.error ?? "Not delivered."}${item.status === null ? "" : ` (${item.status})`}`);
  return { text: summary + failures.join(""), problem: result.delivered !== result.devices };
}

export function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export async function keepPushSubscription(api: Api, publicKey: string | null): Promise<boolean> {
  if (!publicKey || !("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window) || Notification.permission !== "granted") return false;
  try {
    await navigator.serviceWorker.ready;
    const reg = await navigator.serviceWorker.getRegistration();
    const old = await reg?.pushManager.getSubscription();
    if (!reg || !old) return false;
    const key = urlBase64ToUint8Array(publicKey);
    const current = old.options.applicationServerKey;
    const currentBytes = current && new Uint8Array(current);
    if (currentBytes && currentBytes.length === key.length && currentBytes.every((byte, i) => byte === key[i])) {
      await api.pushSubscribe(old.toJSON() as PushSubscriptionIn);
      return true;
    }
    await old.unsubscribe();
    const fresh = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key });
    await api.pushSubscribe(fresh.toJSON() as PushSubscriptionIn);
    try {
      await api.pushUnsubscribe(old.endpoint);
    } catch {
      /* The new device is active even if the server could not remove the old address. */
    }
    return true;
  } catch {
    /* Retry on the next open; Settings shows the device state without showing a background error. */
    return false;
  }
}
