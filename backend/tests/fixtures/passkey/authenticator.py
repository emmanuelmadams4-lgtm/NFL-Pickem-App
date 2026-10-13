"""A software passkey for tests: it answers WebAuthn options the way a phone's authenticator and browser would.

Test code only. It makes the key pair, the authenticator data and the signature so the server's real verification
runs against real bytes. Each knob breaks exactly one thing a real attacker could change.
"""

import hashlib
import json
import os
from base64 import urlsafe_b64encode

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

USER_PRESENT, USER_VERIFIED, HAS_CREDENTIAL = 0x01, 0x04, 0x40


def b64(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


class SoftAuthenticator:
    def __init__(self, rp_id: str, origin: str) -> None:
        self.rp_id = rp_id
        self.origin = origin
        self.key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.count = 0

    @property
    def id(self) -> str:
        return b64(self.credential_id)

    @property
    def cose_public_key(self) -> bytes:
        numbers = self.key.public_key().public_numbers()
        return cbor2.dumps({1: 2, 3: -7, -1: 1, -2: numbers.x.to_bytes(32, "big"), -3: numbers.y.to_bytes(32, "big")})

    def _client_data(self, kind: str, challenge: str, origin: str | None) -> bytes:
        return json.dumps(
            {"type": kind, "challenge": challenge, "origin": origin or self.origin, "crossOrigin": False}
        ).encode()

    def _auth_data(self, rp_id: str | None, uv: bool, count: int, attested: bool) -> bytes:
        flags = USER_PRESENT | (USER_VERIFIED if uv else 0) | (HAS_CREDENTIAL if attested else 0)
        data = hashlib.sha256((rp_id or self.rp_id).encode()).digest() + bytes([flags]) + count.to_bytes(4, "big")
        if attested:
            data += bytes(16) + len(self.credential_id).to_bytes(2, "big") + self.credential_id + self.cose_public_key
        return data

    def create(self, options: dict, *, origin: str | None = None, rp_id: str | None = None, uv: bool = True) -> dict:
        """The body a browser returns from navigator.credentials.create()."""
        auth_data = self._auth_data(rp_id, uv, 0, attested=True)
        attestation = cbor2.dumps({"fmt": "none", "attStmt": {}, "authData": auth_data})
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64(self._client_data("webauthn.create", options["challenge"], origin)),
                "attestationObject": b64(attestation),
                "transports": ["internal"],
            },
        }

    def get(
        self,
        options: dict,
        *,
        origin: str | None = None,
        rp_id: str | None = None,
        uv: bool = True,
        count: int | None = None,
        tamper: str | None = None,
        pad: bool = False,
    ) -> dict:
        """The body a browser returns from navigator.credentials.get(). tamper: 'signature' | 'auth_data'.

        pad: spell the challenge with base64 padding (the same bytes, another spelling).
        """
        self.count = self.count if count is None else count
        auth_data = self._auth_data(rp_id, uv, self.count, attested=False)
        challenge = options["challenge"] + ("=" * (-len(options["challenge"]) % 4) if pad else "")
        client_data = self._client_data("webauthn.get", challenge, origin)
        signature = self.key.sign(auth_data + hashlib.sha256(client_data).digest(), ec.ECDSA(hashes.SHA256()))
        if tamper == "signature":
            signature = signature[:-1] + bytes([signature[-1] ^ 0x01])
        if tamper == "auth_data":  # signed with one counter, sent with another
            auth_data = auth_data[:-4] + (self.count + 100).to_bytes(4, "big")
        return {
            "id": self.id,
            "rawId": self.id,
            "type": "public-key",
            "authenticatorAttachment": "platform",
            "clientExtensionResults": {},
            "response": {
                "clientDataJSON": b64(client_data),
                "authenticatorData": b64(auth_data),
                "signature": b64(signature),
                "userHandle": b64(b"nflpi-owner"),
            },
        }
