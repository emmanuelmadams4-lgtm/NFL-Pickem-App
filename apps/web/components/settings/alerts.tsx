"use client";

import { useCallback, useEffect, useState } from "react";
import { keys, type Meta, type PushSubscriptionIn } from "@nflpi/shared";
import { useQueryClient } from "@tanstack/react-query";
import { useApi } from "@/lib/api";
import { useToast } from "@/components/toast";
import { Button, Chip, Notice, SelectField, Section, errorMessage } from "@/components/ui";

function urlBase64ToUint8Array(base64: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  const out = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function env() {
  const ua = navigator.userAgent;
  const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  const standalone = (navigator as Navigator & { standalone?: boolean }).standalone === true || window.matchMedia("(display-mode: standalone)").matches;
  const pushCapable = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  return { ios, standalone, pushCapable };
}

const REMINDERS = [
  { value: 0, label: "Off" },
  { value: 30, label: "30 minutes before" },
  { value: 60, label: "1 hour before" },
  { value: 180, label: "3 hours before" },
];

export function AlertsSection({ meta }: { meta: Meta }) {
  const api = useApi();
  const qc = useQueryClient();
  const { toast } = useToast();
  const [info, setInfo] = useState<{ ios: boolean; standalone: boolean; pushCapable: boolean; permission: NotificationPermission | null; subscribed: boolean; swReady: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reminderBusy, setReminderBusy] = useState(false);

  const refresh = useCallback(async () => {
    const e = env();
    let subscribed = false;
    let swReady = false;
    if (e.pushCapable) {
      try {
        const reg = await navigator.serviceWorker.getRegistration();
        swReady = !!reg;
        subscribed = !!(await reg?.pushManager.getSubscription());
      } catch {
        /* treat as not subscribed */
      }
    }
    setInfo({ ...e, permission: "Notification" in window ? Notification.permission : null, subscribed, swReady });
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const key = meta.push_public_key;

  async function turnOn() {
    if (!key) return;
    setBusy(true);
    setError(null);
    try {
      const permission = await Notification.requestPermission();
      if (permission !== "granted") {
        // "denied" shows its own standing note below; a dismissed prompt just needs a hint.
        if (permission === "default") setError("Permission was not granted, so alerts stay off.");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(key) });
      await api.pushSubscribe(sub.toJSON() as PushSubscriptionIn);
      qc.invalidateQueries({ queryKey: keys.meta });
      toast("Alerts are on for this device.", "good");
    } catch (e) {
      setError(`Could not turn on alerts. ${errorMessage(e)}`);
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function turnOff() {
    setBusy(true);
    setError(null);
    try {
      const reg = await navigator.serviceWorker.getRegistration();
      const sub = await reg?.pushManager.getSubscription();
      if (sub) {
        const endpoint = sub.endpoint;
        await sub.unsubscribe();
        await api.pushUnsubscribe(endpoint);
      }
      qc.invalidateQueries({ queryKey: keys.meta });
      toast("Alerts are off for this device.", "info");
    } catch (e) {
      setError(`Could not turn off alerts. ${errorMessage(e)}`);
    } finally {
      setBusy(false);
      void refresh();
    }
  }

  async function setReminder(minutes: number) {
    setReminderBusy(true);
    try {
      const updated = await api.updateSettings({ reminder_minutes: minutes });
      qc.setQueryData(keys.meta, updated);
      toast(minutes === 0 ? "Kickoff reminders are off." : `Kickoff reminder set to ${REMINDERS.find((r) => r.value === minutes)?.label.toLowerCase()}.`, "good");
    } catch (e) {
      toast(`Reminder not saved. ${errorMessage(e)}`, "bad");
    } finally {
      setReminderBusy(false);
    }
  }

  let toggle: React.ReactNode;
  if (!info) {
    toggle = <p className="text-sm text-text-2">Checking this device.</p>;
  } else if (!key) {
    toggle = <Notice tone="info">Push not configured on the server (set VAPID keys).</Notice>;
  } else if (!info.pushCapable || (info.ios && !info.standalone)) {
    toggle = <Notice tone="info">On iPhone, add to Home Screen first, then open it from there to turn on alerts.</Notice>;
  } else if (!info.swReady) {
    toggle = <Notice tone="info">Alerts need the installed app build. The service worker is not active here, which is normal in development.</Notice>;
  } else {
    toggle = (
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <Chip tone={info.subscribed ? "good" : "neutral"}>{info.subscribed ? "Alerts on" : "Alerts off"}</Chip>
          {info.subscribed ? (
            <Button onClick={turnOff} loading={busy}>
              Turn off alerts
            </Button>
          ) : (
            <Button variant="primary" onClick={turnOn} loading={busy} disabled={info.permission === "denied"}>
              Turn on alerts
            </Button>
          )}
        </div>
        {info.permission === "denied" && <p className="text-xs text-warn">Notifications are blocked for this app. Allow them in your device settings first.</p>}
        <p className="text-xs text-subtle">
          {meta.push_subscriptions} {meta.push_subscriptions === 1 ? "device is" : "devices are"} subscribed on the server.
        </p>
      </div>
    );
  }

  const reminder = meta.reminder_minutes ?? 0;
  const known = REMINDERS.some((r) => r.value === reminder);

  return (
    <Section id="alerts" title="Alerts" note="Pick flips, big probability moves, QB injury news, and kickoff reminders.">
      <div className="grid gap-x-8 gap-y-5 md:grid-cols-[240px_minmax(0,1fr)]">
        <div>
          <p className="text-sm font-medium text-text">Push notifications</p>
          <p className="mt-0.5 text-xs text-subtle">Delivered to this device, even when the app is closed.</p>
        </div>
        <div className="min-w-0">
          {toggle}
          {error && (
            <p role="alert" className="mt-2 text-sm text-bad">
              {error}
            </p>
          )}
        </div>

        <div>
          <p className="text-sm font-medium text-text">Kickoff reminder</p>
          <p className="mt-0.5 text-xs text-subtle">The server sends a No pick yet alert for games you have not picked.</p>
        </div>
        <div>
          <SelectField label="Remind me" value={reminder} onChange={(e) => setReminder(Number(e.target.value))} disabled={reminderBusy}>
            {!known && <option value={reminder}>{reminder} minutes before</option>}
            {REMINDERS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </SelectField>
        </div>
      </div>
    </Section>
  );
}
