# Stage 1: Production dependencies
# This stage installs production Python dependencies using uv
FROM 856965016623.dkr.ecr.us-east-1.amazonaws.com/root-mirror/python:3.12-alpine3.22 AS python_packages

# Set terminal width (COLUMNS) and height (LINES)
ENV COLUMNS=300

# Configure JFrog Alpine repos, then install secure-apk, rootio-patcher, and uv from apk
# (no public registry pulls -- uv no longer comes from ghcr.io/astral-sh/uv) plus the
# git/jq/build-base/python3-dev this project already needed. uv must come from apk so the
# whole toolchain is sourced from the hardened JFrog/Root.io mirrors, which means this repo
# setup has to run BEFORE `uv sync` (the opposite order from the old ghcr.io-based copy).
#
# Auth: credentials go directly in the /etc/apk/repositories URLs (apk's .netrc support
# does not actually work against this Artifactory endpoint -- confirmed directly: apk
# fails with "Permission denied" against a well-formed .netrc, but succeeds once the same
# credentials are embedded in the repo URL instead), then stripped back out afterward so
# they don't linger in this layer. Matches the working pattern already used by baileyai and
# baileyai-skills-service's Dockerfiles for the same JFrog/Root.io Alpine mirror.
RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    ALPINE_MINOR=$(cat /etc/alpine-release | cut -d. -f1,2) && \
    JF_USER="$(cat /run/secrets/jfrog_read_user)" && \
    JF_TOKEN="$(cat /run/secrets/jfrog_read_token)" && \
    CREDS="${JF_USER}:${JF_TOKEN}" && \
    wget -qO /etc/apk/keys/alpine.rsa.pub \
        "https://${CREDS}@artifacts.bwell.com/artifactory/api/security/keypair/public/repositories/private-alpine" && \
    wget -qO "/etc/apk/keys/root@alpinelinux.org.rsa.pub" \
        "https://${CREDS}@artifacts.bwell.com/artifactory/vendor-public-keys/rootio-alpine.pub" && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/rootio-alpine/${ALPINE_MINOR}"            >  /etc/apk/repositories && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/global-alpine/v${ALPINE_MINOR}/main"      >> /etc/apk/repositories && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/global-alpine/v${ALPINE_MINOR}/community" >> /etc/apk/repositories && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/private-alpine/main/${ALPINE_MINOR}"      >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache secure-apk rootio-patcher uv git jq build-base python3-dev && \
    sed -i 's|https://[^@]*@|https://|g' /etc/apk/repositories

# Set environment variables for uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Set the working directory inside the container
WORKDIR /usr/src/patient_matching/

# Copy pyproject.toml and uv.lock to the working directory
COPY pyproject.toml uv.lock* /usr/src/patient_matching/

# Install all production dependencies using uv. Auth via JFrog index env vars -- uv reads
# UV_INDEX_JFROG_USERNAME/PASSWORD ("jfrog" is the index name in pyproject.toml), passed as
# BuildKit secrets, never written to disk. Uses the real JFROG_READ_USER, not an empty
# string -- Artifactory's virtual-pypi rejects an empty username with 403 even given a
# valid token as the password (confirmed directly against this same index elsewhere).
RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    set -eu; \
    export UV_INDEX_JFROG_USERNAME="$(cat /run/secrets/jfrog_read_user)"; \
    export UV_INDEX_JFROG_PASSWORD="$(cat /run/secrets/jfrog_read_token)"; \
    uv sync --frozen --all-extras --no-install-project --verbose

# Validate dependencies against the Root.io vulnerability database (dry-run only).
# rootio_patcher inspects the venv via `python -m pip list`, but uv-created venvs omit
# pip. Bootstrapping it via `python -m ensurepip` (as this used to do) fails outright on
# this base image: its local bundled wheel cache is missing a rootio_setuptools wheel its
# own package list still demands, and its CLI no longer accepts --no-setuptools to skip
# that package (confirmed directly; same root cause baileyai hit as BAI-531). uv needs no
# existing pip to install into a venv, so install a pinned vanilla pip with uv itself
# instead, sidestepping ensurepip entirely -- same fix as baileyai's Dockerfile. pip is
# only here to satisfy rootio_patcher's inventory and is never copied to a runtime image
# (only /opt/venv is copied forward).
RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    uv pip install --python /opt/venv/bin/python --no-cache \
    --index-url "https://$(cat /run/secrets/jfrog_read_user):$(cat /run/secrets/jfrog_read_token)@artifacts.bwell.com/artifactory/api/pypi/virtual-pypi/simple" \
    "pip==26.2.1" && \
    ROOTIO_PKG_URL=https://artifacts.bwell.com/artifactory/api \
    ROOTIO_PIP_INDEX_URL=https://artifacts.bwell.com/artifactory/api/pypi/virtual-pypi/simple \
    rootio_patcher pip remediate --dry-run --python-path=/opt/venv/bin/python

# Remove JFrog credentials (this stage is discarded; only /opt/venv is copied forward)
RUN rm -rf ~/.netrc

# Copy uv.lock from working directory to /tmp for retrieval if needed
RUN cp -n /usr/src/patient_matching/uv.lock /tmp/uv.lock

# Stage 1b: Development dependencies (extends production)
# This stage installs dev dependencies on top of production
FROM python_packages AS python_packages_dev

RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    set -eu; \
    export UV_INDEX_JFROG_USERNAME="$(cat /run/secrets/jfrog_read_user)"; \
    export UV_INDEX_JFROG_PASSWORD="$(cat /run/secrets/jfrog_read_token)"; \
    uv sync --frozen --all-extras --group dev --no-install-project --verbose

# Stage 2: Production runtime image
FROM 856965016623.dkr.ecr.us-east-1.amazonaws.com/root-mirror/python:3.12-alpine3.22 AS production

# Set terminal width (COLUMNS) and height (LINES)
ENV COLUMNS=300

# Configure JFrog Alpine repos (credentials embedded in the repo URLs, then stripped back
# out at the end of this RUN so they don't persist in this stage's layers, since this stage
# IS a shipped image, not a discarded builder stage) and install runtime OS deps from the
# hardened mirror instead of the public Alpine CDN. Same auth pattern as the builder stage
# above -- see the comment there for why .netrc doesn't work here.
RUN --mount=type=secret,id=jfrog_read_user --mount=type=secret,id=jfrog_read_token \
    ALPINE_MINOR=$(cat /etc/alpine-release | cut -d. -f1,2) && \
    JF_USER="$(cat /run/secrets/jfrog_read_user)" && \
    JF_TOKEN="$(cat /run/secrets/jfrog_read_token)" && \
    CREDS="${JF_USER}:${JF_TOKEN}" && \
    wget -qO /etc/apk/keys/alpine.rsa.pub \
        "https://${CREDS}@artifacts.bwell.com/artifactory/api/security/keypair/public/repositories/private-alpine" && \
    wget -qO "/etc/apk/keys/root@alpinelinux.org.rsa.pub" \
        "https://${CREDS}@artifacts.bwell.com/artifactory/vendor-public-keys/rootio-alpine.pub" && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/rootio-alpine/${ALPINE_MINOR}"            >  /etc/apk/repositories && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/global-alpine/v${ALPINE_MINOR}/main"      >> /etc/apk/repositories && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/global-alpine/v${ALPINE_MINOR}/community" >> /etc/apk/repositories && \
    echo "https://${CREDS}@artifacts.bwell.com/artifactory/private-alpine/main/${ALPINE_MINOR}"      >> /etc/apk/repositories && \
    apk update && \
    apk add --no-cache git libstdc++ && \
    sed -i 's|https://[^@]*@|https://|g' /etc/apk/repositories

# Set environment variables for project configuration
ENV PROJECT_DIR=/usr/src/patient_matching
ENV FLASK_APP=patient_matching.api
ENV PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create the directory for Prometheus metrics
RUN mkdir -p ${PROMETHEUS_MULTIPROC_DIR}

# Set the working directory for the project
WORKDIR ${PROJECT_DIR}

# Copy the application code into the runtime image (NO tests directory)
COPY ./patient_matching ${PROJECT_DIR}/patient_matching

# Copy installed Python packages from the previous stage
COPY --from=python_packages /opt/venv /opt/venv

# Copy uv.lock to a temporary directory so it can be retrieved if needed
COPY --from=python_packages /tmp/uv.lock /tmp/uv.lock

# Expose port 5000 for the application
EXPOSE 5000

# Switch to the root user to perform user management tasks
USER root

# Create a restricted user (appuser) and group (appgroup) for running the application
RUN addgroup -S appgroup && adduser -S -h /etc/appuser appuser -G appgroup

# Ensure that the appuser owns the application files and directories
RUN chown -R appuser:appgroup ${PROJECT_DIR} /opt/venv ${PROMETHEUS_MULTIPROC_DIR}

# Switch to the restricted user to enhance security
USER appuser

# Stage 3: Development runtime (extends production with dev deps, tests, and hot reload)
FROM production AS development

USER root
# Copy dev dependencies (superset of production)
COPY --from=python_packages_dev /opt/venv /opt/venv
# Tests are inside the package subdirectories, no need to copy单独 tests directory
RUN chown -R appuser:appgroup /opt/venv ${PROJECT_DIR}
USER appuser

# Override CMD with hot-reload for local development
CMD ["uvicorn", "patient_matching.api:app", "--host", "0.0.0.0", "--port", "5000", "--reload"]

# Default: bare `docker build .` produces production image
FROM production
