"""FastAPI application for patient matching.

Exposes two endpoints:
  - POST /Patient/$match — FHIR $match operation
  - POST /match/ial2 — Match from an IAL2 JWT token
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .service import MatchResponse, PatientMatcherService

logger = logging.getLogger(__name__)


def create_app(
    *,
    service: PatientMatcherService,
    title: str = "Patient Matching Service",
    version: str = "1.0.0",
) -> FastAPI:
    """Create the FastAPI application.

    Args:
        service: The patient matching service instance.
        title: Application title.
        version: Application version.

    Returns:
        A configured FastAPI application.
    """
    app = FastAPI(title=title, version=version)

    @app.post(
        "/Patient/$match",
        response_class=JSONResponse,
        summary="FHIR $match operation",
        description=(
            "Accepts a FHIR Parameters resource containing a Patient "
            "resource and returns a Bundle of matching patients."
        ),
    )
    async def fhir_match(request: Request) -> JSONResponse:
        """FHIR $match endpoint.

        Expects a FHIR Parameters resource with a ``resource``
        parameter containing a Patient resource.

        Returns a FHIR Bundle (searchset) with matched patients
        and match confidence scores.
        """
        body = await request.body()
        try:
            params_dict = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON: {exc}",
            )

        # Extract the Patient resource from Parameters
        patient_dict = _extract_patient_from_parameters(params_dict)
        if patient_dict is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Parameters resource must contain a 'resource' "
                    "parameter with a Patient resource."
                ),
            )

        # Match
        result = service.match_patient(patient_dict)

        # Build FHIR Bundle response
        bundle = _build_match_bundle(result)
        return JSONResponse(
            content=bundle,
            media_type="application/fhir+json",
        )

    @app.post(
        "/match/ial2",
        response_class=JSONResponse,
        summary="Match from IAL2 token",
        description=(
            "Accepts a signed IAL2 JWT token and returns matched FHIR Patient IDs."
        ),
    )
    async def match_ial2(request: Request) -> JSONResponse:
        """IAL2 token matching endpoint.

        Expects a JSON body with ``{"token": "<jwt>"}`` or a raw
        JWT string in the request body.
        """
        body = await request.body()
        body_str = body.decode("utf-8").strip()

        # Accept either {"token": "..."} or raw JWT
        if body_str.startswith("{"):
            try:
                data = json.loads(body_str)
                token = data["token"]
            except (json.JSONDecodeError, KeyError):
                raise HTTPException(
                    status_code=400,
                    detail='Expected JSON body with "token" field.',
                )
        else:
            token = body_str

        if not token:
            raise HTTPException(status_code=400, detail="Token is required.")

        try:
            result = service.match_from_token(token)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.exception("Token matching failed")
            raise HTTPException(
                status_code=401,
                detail=f"Token verification failed: {exc}",
            )

        # Build FHIR Bundle response
        bundle = _build_match_bundle(result)
        return JSONResponse(
            content=bundle,
            media_type="application/fhir+json",
        )

    @app.get(
        "/health",
        summary="Health check",
    )
    async def health() -> Dict[str, str]:
        return {"status": "ok"}

    return app


def _extract_patient_from_parameters(
    params_dict: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Extract the Patient resource from a FHIR Parameters dict."""
    if params_dict.get("resourceType") != "Parameters":
        return None

    for param in params_dict.get("parameter", []):
        if param.get("name") == "resource":
            resource: Dict[str, Any] = param.get("resource", {})
            if resource.get("resourceType") == "Patient":
                return resource
    return None


def _build_match_bundle(result: MatchResponse) -> Dict[str, Any]:
    """Build a FHIR Bundle (searchset) dict from a MatchResponse."""
    entries: List[Dict[str, Any]] = []
    for patient_dict in result.matched_patients:
        patient_id = patient_dict.get("id", "")
        entry: Dict[str, Any] = {
            "resource": patient_dict,
            "search": {
                "mode": "match",
                "score": result.confidence_score,
            },
        }
        if patient_id:
            entry["fullUrl"] = f"Patient/{patient_id}"
        entries.append(entry)

    bundle: Dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
    }
    if entries:
        bundle["entry"] = entries

    return bundle
