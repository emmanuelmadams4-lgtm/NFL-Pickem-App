const unsupported = "This browser cannot use a passkey here. Use your access token.";

type JsonPasskey = PublicKeyCredential & { toJSON: () => unknown };
type JsonPasskeyConstructor = typeof PublicKeyCredential & {
  parseCreationOptionsFromJSON?: (options: Record<string, unknown>) => PublicKeyCredentialCreationOptions;
  parseRequestOptionsFromJSON?: (options: Record<string, unknown>) => PublicKeyCredentialRequestOptions;
};

export function passkeyReady(kind: "create" | "get"): boolean {
  if (typeof PublicKeyCredential === "undefined" || typeof navigator === "undefined" || !navigator.credentials) return false;
  const ctor = PublicKeyCredential as JsonPasskeyConstructor;
  const parser = kind === "create" ? ctor.parseCreationOptionsFromJSON : ctor.parseRequestOptionsFromJSON;
  return typeof parser === "function" && typeof (ctor.prototype as JsonPasskey).toJSON === "function";
}

export const passkeyUnsupported = unsupported;

export async function createPasskey(options: Record<string, unknown>): Promise<unknown> {
  const ctor = PublicKeyCredential as JsonPasskeyConstructor;
  const publicKey = ctor.parseCreationOptionsFromJSON!(options);
  const credential = await navigator.credentials.create({ publicKey });
  if (!credential || typeof (credential as JsonPasskey).toJSON !== "function") throw new Error(unsupported);
  return (credential as JsonPasskey).toJSON();
}

export async function getPasskey(options: Record<string, unknown>): Promise<unknown> {
  const ctor = PublicKeyCredential as JsonPasskeyConstructor;
  const publicKey = ctor.parseRequestOptionsFromJSON!(options);
  const credential = await navigator.credentials.get({ publicKey });
  if (!credential || typeof (credential as JsonPasskey).toJSON !== "function") throw new Error(unsupported);
  return (credential as JsonPasskey).toJSON();
}

export function passkeyCancelled(error: unknown): boolean {
  return error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "AbortError");
}
