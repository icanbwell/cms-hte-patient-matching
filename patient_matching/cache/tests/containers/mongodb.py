"""MongoDB Atlas Local test container for MongoAtlasCache tests.

Adapted from person-matching-service's tests/containers/mongodb.py (session_12
Upstream data/system dependencies: the ``mongodb/mongodb-atlas-local:8.0.13``
image bundles ``mongot``, so Atlas Search is testable without a real Atlas
cluster). Atlas Local is a replica set; the external URL must use
directConnection=true because the set advertises an internal hostname
unreachable from outside its own network.

``connection_string`` picks external vs. internal URL automatically: see
``network.self_container_id`` for why -- pytest running inside this repo's
``dev`` container (docker-outside-of-docker) can't reach the sibling mongo
container's host-mapped port, only its network alias.
"""

import logging
from collections.abc import Generator
from dataclasses import dataclass

import docker
import pytest
from docker.models.networks import Network
from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import ExecWaitStrategy

from .network import self_container_id

logger = logging.getLogger(__name__)

_MONGO_IMAGE = "mongodb/mongodb-atlas-local:8.0.13"
_MONGO_PORT = 27017
_ALIAS = "mongo"
_MONGO_USER = "root"
_MONGO_PASS = "test123"  # pragma: allowlist secret


@dataclass
class MongoDBService:
    external_url: str  # mongodb://<user>:<pass>@<host>:<port>/?directConnection=true
    internal_url: str  # mongodb://mongo:27017 (container -> container)
    username: str = _MONGO_USER
    password: str = _MONGO_PASS

    @property
    def connection_string(self) -> str:
        """The URL usable from wherever pytest itself is running."""
        if self_container_id() is not None:
            return self.internal_url
        return self.external_url


def _start_mongo(network: Network) -> tuple[DockerContainer, MongoDBService]:
    logger.info("Pre-pulling MongoDB image %s ...", _MONGO_IMAGE)
    pull_client = docker.from_env(timeout=300)
    try:
        repo, tag = _MONGO_IMAGE.rsplit(":", 1)
        pull_client.images.pull(repo, tag)
    finally:
        pull_client.close()

    # A plain mongod ping only proves mongod is up; mongot (the search process
    # bundled in this image) starts later and isn't covered by it. `runner
    # healthcheck` is the image's own combined mongod+mongot readiness check.
    ready = ExecWaitStrategy(["runner", "healthcheck"]).with_startup_timeout(120)

    mongo = DockerContainer(image=_MONGO_IMAGE, docker_client_kw={"timeout": 300})
    mongo.with_exposed_ports(_MONGO_PORT)
    mongo.with_env("MONGODB_INITDB_ROOT_USERNAME", _MONGO_USER)
    mongo.with_env("MONGODB_INITDB_ROOT_PASSWORD", _MONGO_PASS)
    mongo = mongo.with_network(network).with_network_aliases(_ALIAS).waiting_for(ready)
    mongo.start()

    host = mongo.get_container_host_ip()
    port = mongo.get_exposed_port(_MONGO_PORT)
    external_url = (
        f"mongodb://{_MONGO_USER}:{_MONGO_PASS}@{host}:{port}/?directConnection=true"
    )
    internal_url = (
        f"mongodb://{_MONGO_USER}:{_MONGO_PASS}@{_ALIAS}:{_MONGO_PORT}"
        "/?directConnection=true"
    )

    svc = MongoDBService(external_url=external_url, internal_url=internal_url)
    logger.info(
        "MongoDB ready — external=%s internal=%s", svc.external_url, svc.internal_url
    )
    return mongo, svc


@pytest.fixture(scope="session")
def mongodb(docker_network: Network) -> Generator[MongoDBService]:
    container, svc = _start_mongo(docker_network)
    try:
        yield svc
    finally:
        container.stop()
