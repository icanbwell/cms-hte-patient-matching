"""Shared Docker network for MongoAtlasCache's testcontainer tests.

Adapted from person-matching-service's tests/containers/network.py (same
underlying pattern, referenced in session_12.md's Upstream data/system
dependencies). One addition not needed there: person-matching-service runs
its tests directly on the host via ``uv run pytest``, so its containers'
host-mapped ports are always reachable. This repo's ``make tests`` runs
pytest *inside* the ``dev`` container (docker-outside-of-docker, via the
mounted host docker.sock -- see docker-compose.yml), so a container started
here binds its ports on the real host, not inside ``dev``'s network
namespace. ``self_container_id`` lets a fixture attach ``dev`` itself to
this network so it can reach sibling containers by alias instead.
"""

import logging
import os
import socket
from collections.abc import Generator

import docker
import pytest
from docker.models.networks import Network

logger = logging.getLogger(__name__)

_NETWORK_NAME = "cms-hte-patient-matching-test-net"


def self_container_id() -> str | None:
    """Return this process's own container ID, or None if not containerized.

    Docker sets a container's hostname to its short container ID unless
    overridden; ``/.dockerenv`` is the standard marker for "running inside
    a container at all" (vs. a host running `uv run pytest` directly, where
    joining a test network is unnecessary -- host-mapped ports already work).
    """
    if not os.path.exists("/.dockerenv"):
        return None
    return socket.gethostname()


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

    If pytest itself is running inside a container (see ``self_container_id``),
    attaches that container to the network too, so it can reach sibling test
    containers (e.g. mongodb) by network alias.

    Skips (rather than erroring) if no Docker daemon is reachable -- e.g. a
    contributor's machine without Colima/Docker Desktop running.
    """
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:
        pytest.skip(f"Docker is not available, skipping container tests: {exc}")

    network = _get_or_create_network(client)
    own_id = self_container_id()
    if own_id is not None:
        try:
            network.connect(own_id)
            logger.info("Attached own container %s to %s", own_id, network.name)
        except docker.errors.APIError as exc:
            logger.warning(
                "Could not attach own container %s to %s: %s",
                own_id,
                network.name,
                exc,
            )
    try:
        yield network
    finally:
        _remove_network(network)
