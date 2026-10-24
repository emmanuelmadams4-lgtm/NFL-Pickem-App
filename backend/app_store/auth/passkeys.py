"""Passkey WebAuthn helpers.

Minimal WebAuthn implementation for the admin UI (passkey registration + login).
Uses the `webauthn` PyPI package. The WebAuthn RP (relying party) is this host.
"""

from __future__ import annotations

import base64
import os
from typing import Any

from webauthn.helpers import helpers
from webauthn.helpers.types import (
    AuthenticationCredential,
    PublicKeyCredentialDescriptor,
    RegistrationCredential,
    AttestationConveyancePreference,
    AttestationObject,
    ClientData,
    UserVerificationRequirement,
)
from webauthn import WebAuthn as WebAuthnClass
from webauthn.oidc import Fqi, Pqi

# RP ID must match what the browser uses (tailscale ip or .ts.net host)
DEFAULT_RP_ID = "localhost"


class WebAuthn:
    def __init__(self, rp_id: str = DEFAULT_RP_ID, origins: str = "http://localhost,https://localhost"):
        self.rp_id = rp_id
        self.origins = [o.strip() for o in origins.split(",")]
        self.webauthn = WebAuthnClass(rp_id=rp_id, origins=self.origins)

    def get_registration_challenge(self, user_id: str, display_name: str) -> tuple[str, dict[str, Any]]:
        """Create a registration challenge for the given user."""
        user = {
            "id": user_id.encode(),
            "name": user_id,
            "display_name": display_name,
        }
        registration = self.webauthn.register(user, relying_party_id=self.rp_id)
        challenge = helpers.parse_registration_data(registration)
        return challenge, {
            "raw_id": base64.urlsafe_b64encode(user["id"]).decode(),
            "public_key": base64.urlsafe_b64encode(registration.public_key).decode(),
            "sign_count": 0,
            "key_type": "public-key",
            "transports": registration.transports or [],
        }

    def verify_registration(self, user_id: str, request_json: dict[str, Any]) -> dict[str, Any]:
        """Verify a registration response and return the credential."""
        raw_id = base64.urlsafe_b64decode(request_json["raw_id"])
        credential_dict = {
            "id": raw_id,
            "raw_id": raw_id,
            "response": {
                "attestation_object": base64.urlsafe_b64decode(request_json["attestation_object"]),
                "client_data_json": base64.urlsafe_b64decode(request_json["client_data_json"]),
            },
            "authenticator_data": request_json.get("authenticator_data", ""),
            "client_data_json": request_json.get("client_data_json", ""),
        }

        # WebAuthn expects the credential with a specific structure
        cred = RegistrationCredential(**credential_dict)
        result = self.webauthn.verify_registration(cred, user_id, self.rp_id)

        return {
            "id": result.credential_id.hex(),
            "raw_id": result.credential_id.hex(),
            "public_key": base64.urlsafe_b64encode(result.credential_public_key).decode(),
            "sign_count": result.sign_count,
            "key_type": "public-key",
            "transports": result.transports,
        }

    def get_authentication_challenge(self, user_id: str) -> tuple[str, dict[str, Any]]:
        """Create an authentication challenge for the given user."""
        # In a real application, look up the user by user_id and return their
        # registered credentials. For simplicity, we return a challenge.
        challenge = self.webauthn.get_authentication_challenge(user_id)
        return challenge, {
            "challenge": challenge,
            "rp_id": self.rp_id,
            "timeout": 60000,
            "allow_credentials": [],  # filled by frontend
        }

    def verify_assertion(self, credential_id: str, request_json: dict[str, Any], recorded_sign_count: int) -> bool:
        """Verify an authentication response (login)."""
        try:
            raw_id = bytes.fromhex(credential_id)
            credential_dict = {
                "id": raw_id,
                "raw_id": raw_id,
                "response": {
                    "authenticator_data": request_json.get("authenticator_data", ""),
                    "client_data_json": base64.urlsafe_b64decode(request_json["client_data_json"]),
                    "signature": base64.urlsafe_b64decode(request_json["signature"]),
                    "user_handle": request_json.get("user_handle", ""),
                },
                "authenticator_data": request_json.get("authenticator_data", ""),
                "client_data_json": request_json.get("client_data_json", ""),
                "signature": request_json.get("signature", ""),
                "user_handle": request_json.get("user_handle", ""),
            }

            cred = AuthenticationCredential(**credential_dict)
            result = self.webauthn.verify_authentication(cred, self.rp_id)

            # Verify sign count (replay protection)
            if result.new_sign_count <= recorded_sign_count:
                return False

            return True
        except Exception:
            return False
