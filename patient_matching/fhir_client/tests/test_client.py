"""Tests for the FHIR client."""

import json
from typing import Any, Dict, List, Union
from unittest.mock import MagicMock, patch


from patient_matching.fhir_client.client import FhirClient, FhirClientConfig


def _make_bundle(
    patients: List[Dict[str, Any]], next_url: Union[str, None] = None
) -> Dict[str, Any]:
    """Create a FHIR Bundle dict with patient entries."""
    entries = []
    for p in patients:
        entries.append(
            {
                "fullUrl": f"Patient/{p['id']}",
                "resource": p,
            }
        )

    bundle: Dict[str, Any] = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(patients),
        "entry": entries,
    }

    if next_url:
        bundle["link"] = [{"relation": "next", "url": next_url}]

    return bundle


def _make_patient(
    patient_id: str = "patient-1", first: str = "john", last: str = "smith"
) -> Dict[str, Any]:
    return {
        "resourceType": "Patient",
        "id": patient_id,
        "name": [{"family": last, "given": [first]}],
        "birthDate": "1990-01-15",
    }


def _mock_response(data_dict: Dict[str, Any], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = data_dict
    resp.text = json.dumps(data_dict)
    resp.status_code = status_code
    return resp


def _setup_mock_http(
    client: FhirClient, responses: Union[MagicMock, List[MagicMock]]
) -> MagicMock:
    """Set up a mock HTTP client that returns the given responses."""
    mock_http_client = MagicMock()
    mock_http_client.__enter__ = MagicMock(return_value=mock_http_client)
    mock_http_client.__exit__ = MagicMock(return_value=False)
    if isinstance(responses, list):
        mock_http_client.get.side_effect = responses
    else:
        mock_http_client.get.return_value = responses
    return mock_http_client


class TestFhirClient:
    def test_fetch_all_patients_single_page(self) -> None:
        patients = [_make_patient("p1"), _make_patient("p2")]
        bundle = _make_bundle(patients)

        config = FhirClientConfig(base_url="https://fhir.example.com/R4")
        client = FhirClient(config)

        mock_http_client = _setup_mock_http(client, _mock_response(bundle))

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            result = list(client.fetch_all_patients())

        assert len(result) == 2
        assert result[0]["id"] == "p1"
        assert result[1]["id"] == "p2"

    def test_fetch_all_patients_pagination(self) -> None:
        page1 = _make_bundle(
            [_make_patient("p1")],
            next_url="https://fhir.example.com/R4/Patient?_page=2",
        )
        page2 = _make_bundle([_make_patient("p2")])

        config = FhirClientConfig(base_url="https://fhir.example.com/R4")
        client = FhirClient(config)

        mock_http_client = _setup_mock_http(
            client, [_mock_response(page1), _mock_response(page2)]
        )

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            result = list(client.fetch_all_patients())

        assert len(result) == 2
        assert result[0]["id"] == "p1"
        assert result[1]["id"] == "p2"

    def test_fetch_all_patients_max_pages(self) -> None:
        page = _make_bundle(
            [_make_patient("p1")],
            next_url="https://fhir.example.com/R4/Patient?_page=2",
        )

        config = FhirClientConfig(
            base_url="https://fhir.example.com/R4",
            max_pages=1,
        )
        client = FhirClient(config)

        mock_http_client = _setup_mock_http(client, _mock_response(page))

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            result = list(client.fetch_all_patients())

        # Should stop after 1 page even though there's a next link
        assert len(result) == 1

    def test_fetch_patient_by_id(self) -> None:
        patient = _make_patient("p-123")

        config = FhirClientConfig(base_url="https://fhir.example.com/R4")
        client = FhirClient(config)

        mock_http_client = _setup_mock_http(client, _mock_response(patient))

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            result = client.fetch_patient("p-123")

        assert result is not None
        assert result["id"] == "p-123"

    def test_fetch_patient_not_found(self) -> None:
        config = FhirClientConfig(base_url="https://fhir.example.com/R4")
        client = FhirClient(config)

        mock_http_client = _setup_mock_http(client, _mock_response({}, status_code=404))

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            result = client.fetch_patient("nonexistent")

        assert result is None

    def test_auth_header_included(self) -> None:
        mock_auth = MagicMock()
        config = FhirClientConfig(
            base_url="https://fhir.example.com/R4",
            auth=mock_auth,
        )
        mock_auth.get_access_token.return_value = "bearer-token-xyz"

        client = FhirClient(config)
        bundle = _make_bundle([_make_patient("p1")])

        mock_http_client = _setup_mock_http(client, _mock_response(bundle))

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            list(client.fetch_all_patients())

        # Verify auth header was set
        call_args = mock_http_client.get.call_args
        headers = call_args.kwargs.get("headers", {})
        assert headers["Authorization"] == "Bearer bearer-token-xyz"

    def test_empty_bundle(self) -> None:
        bundle = {"resourceType": "Bundle", "type": "searchset", "total": 0}

        config = FhirClientConfig(base_url="https://fhir.example.com/R4")
        client = FhirClient(config)

        mock_http_client = _setup_mock_http(client, _mock_response(bundle))

        with patch.object(client, "_create_http_client", return_value=mock_http_client):
            result = list(client.fetch_all_patients())

        assert len(result) == 0
