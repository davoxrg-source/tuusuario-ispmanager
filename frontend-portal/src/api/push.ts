import { apiClient } from "./client";

export async function getVapidPublicKey(): Promise<string> {
  const { data } = await apiClient.get<{ public_key: string }>("/vapid-public-key");
  return data.public_key;
}

async function subscribeToPush(subscription: PushSubscription): Promise<void> {
  await apiClient.post("/push-subscriptions", subscription.toJSON());
}

async function unsubscribeFromPush(endpoint: string): Promise<void> {
  await apiClient.delete("/push-subscriptions", { params: { endpoint } });
}

// El navegador exige la applicationServerKey como Uint8Array, no como el
// string base64url que maneja el resto de la app -- conversión estándar
// del ejemplo oficial de Web Push.
function urlBase64ToUint8Array(base64url: string): Uint8Array {
  const padding = "=".repeat((4 - (base64url.length % 4)) % 4);
  const base64 = (base64url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function isPushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window;
}

export async function getCurrentPushSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

export async function enablePush(): Promise<void> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error("Permiso de notificaciones denegado.");
  }
  const publicKey = await getVapidPublicKey();
  if (!publicKey) {
    throw new Error("El servidor todavía no tiene notificaciones push configuradas.");
  }
  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey) as BufferSource,
  });
  await subscribeToPush(subscription);
}

export async function disablePush(): Promise<void> {
  const subscription = await getCurrentPushSubscription();
  if (!subscription) return;
  await unsubscribeFromPush(subscription.endpoint);
  await subscription.unsubscribe();
}
