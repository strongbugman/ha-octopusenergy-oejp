from __future__ import annotations

from octopusenergy_oejp_demo.client import OctopusOejpClient
from octopusenergy_oejp_demo.discovery import discover_account_electricity_data

from .conftest import Route


def test_discovery_extracts_identifiers_and_records_endpoint_status(fake_transport_factory):
    transport = fake_transport_factory(
        [
            Route("POST", "/v1/auth/login/", 200, {"access": "secret-token"}),
            Route(
                "GET",
                "/v1/accounts/",
                200,
                {
                    "results": [
                        {
                            "account_number": "A-123",
                            "properties": [{"property_id": "P-456"}],
                            "electricity_meter_points": [
                                {"mpan": "MP-789", "meters": [{"serial_number": "M-0001"}]}
                            ],
                        }
                    ]
                },
            ),
            Route("GET", "/v1/me/", 404, {"detail": "not found"}),
            Route("GET", "/v1/customer/", 404, {"detail": "not found"}),
            Route("GET", "/v1/customers/me/", 404, {"detail": "not found"}),
            Route("GET", "/v1/properties/", 404, {"detail": "not found"}),
            Route("GET", "/v1/electricity-meter-points/", 404, {"detail": "not found"}),
            Route("GET", "/v1/accounts/A-123/", 200, {"number": "A-123"}),
            Route("GET", "/v1/accounts/A-123/properties/", 200, {"results": [{"property_id": "P-456"}]}),
            Route(
                "GET",
                "/v1/accounts/A-123/electricity-meter-points/",
                200,
                {"results": [{"meter_point_id": "MP-789", "meter_serial_number": "M-0001"}]},
            ),
            Route(
                "GET",
                "/v1/electricity-meter-points/MP-789/meters/M-0001/consumption/",
                200,
                {"results": [{"kwh": "1.2"}]},
            ),
        ]
    )
    client = OctopusOejpClient(
        email="person@example.com",
        password="not-printed",
        base_url="https://api.example.test",
        auth_paths=("/v1/auth/login/",),
        transport=transport,
    )

    report = discover_account_electricity_data(client, max_derived_requests=50)
    summary = report.summary(raw_output_path=".local/raw.json")

    assert report.authenticated is True
    assert report.accounts == {"A-123"}
    assert report.properties == {"P-456"}
    assert report.meter_points == {"MP-789"}
    assert report.meters == {"M-0001"}
    assert summary["endpoint_counts"]["successful"] >= 4
    assert summary["endpoint_counts"]["failed"] >= 1
    assert "/v1/auth/login/" not in [payload["path"] for payload in report.raw_payloads.values()]
    assert all("A-123" not in endpoint["path"] for endpoint in summary["endpoint_results"])


def test_discovery_returns_redacted_auth_error(fake_transport_factory):
    transport = fake_transport_factory(
        [
            Route("POST", "/v1/auth/login/", 401, {"detail": "bad credentials"}),
        ]
    )
    client = OctopusOejpClient(
        email="person@example.com",
        password="not-printed",
        base_url="https://api.example.test",
        auth_paths=("/v1/auth/login/",),
        transport=transport,
    )

    report = discover_account_electricity_data(client)
    summary = report.summary()

    assert summary["authenticated"] is False
    assert "auth_error" in summary
    assert "not-printed" not in str(summary)
    assert "person@example.com" not in str(summary)
