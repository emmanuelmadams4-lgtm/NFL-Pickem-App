export const passkeyUnsupported = "This browser cannot use a passkey here. Use your access token.";

export class PasskeyBrowserError extends Error {
  constructor() {
    super("Your browser refused the passkey.");
  }
}

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

function credentialJson(credential: Credential | null): unknown {
  if (!credential || typeof (credential as JsonPasskey).toJSON !== "function") throw new Error(passkeyUnsupported);
  return (credential as JsonPasskey).toJSON();
}

function browserFailure(error: unknown, preserveInvalidState: boolean): never {
  if (passkeyCancelled(error) || (error instanceof Error && error.message === passkeyUnsupported)) throw error;
  if (preserveInvalidState && error instanceof DOMException && error.name === "InvalidStateError") throw error;
  throw new PasskeyBrowserError();
}

export async function createPasskey(options: Record<string, unknown>): Promise<unknown> {
  try {
    const ctor = PublicKeyCredential as JsonPasskeyConstructor;
    const publicKey = ctor.parseCreationOptionsFromJSON!(options);
    const credential = await navigator.credentials.create({ publicKey });
    return credentialJson(credential);
  } catch (error) {
    browserFailure(error, true);
  }
}

export async function getPasskey(options: Record<string, unknown>): Promise<unknown> {
  try {
    const ctor = PublicKeyCredential as JsonPasskeyConstructor;
    const publicKey = ctor.parseRequestOptionsFromJSON!(options);
    const credential = await navigator.credentials.get({ publicKey });
    return credentialJson(credential);
  } catch (error) {
    browserFailure(error, false);
  }
}

export function passkeyCancelled(error: unknown): boolean {
  return error instanceof DOMException && (error.name === "NotAllowedError" || error.name === "AbortError");
}
