"""Shared Docker network for MongoAtlasCache's testcontainer tests.

Adapted from person-matching-service's tests/containers/network.py (same
underlying pattern, referenced in session_12.md's Upstream data/system
dependencies). pytest runs directly on the host via ``uv run pytest`` (no
Docker layer of its own -- see session_14.md), so this network exists only
to isolate this repo's test containers from unrelated ones, not to let a
containerized test process reach a sibling container by alias.
"""

import logging
from collections.abc import Generator

import docker
import pytest
from docker.models.networks import Network

logger = logging.getLogger(__name__)

_NETWORK_NAME = "cms-hte-patient-matching-test-net"


def _remove_network(network: Network) -> None:
    """Force-disconnect any attached containers and remove the network.

    Best-effort: a Docker network cannot be removed while containers are
    still attached, so each is disconnected first. Failures are logged, not
    raised -- this runs during setup (stale cleanup) and teardown, where a
    failed removal must not abort the test session.
    """
    try:
        network.reload()
        for container in network.containers:
            try:
                network.disconnect(container, force=True)
            except Exception:
                pass
        network.remove()
        logger.info("Removed Docker network %s", _NETWORK_NAME)
    except Exception as exc:
        logger.warning("Could not remove network %s: %s", _NETWORK_NAME, exc)


def _get_or_create_network(client: docker.DockerClient) -> Network:
    """Return the test network, removing any stale copy first."""
    for net in client.networks.list(names=[_NETWORK_NAME]):
        _remove_network(net)

    network = client.networks.create(_NETWORK_NAME, driver="bridge")
    logger.info("Created Docker network %s (%s)", network.name, network.short_id)
    return network


@pytest.fixture(scope="session")
def docker_network() -> Generator[Network]:
    """Create a Docker bridge network, tear it down at session end.

    Skips (rather than erroring) if no Docker daemon is reachable -- e.g. a
    contributor's machine without Colima/Docker Desktop running.
    """
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:
        pytest.skip(f"Docker is not available, skipping container tests: {exc}")

    network = _get_or_create_network(client)
    try:
        yield network
    finally:
        _remove_network(network)
