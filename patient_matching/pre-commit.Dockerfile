FROM public.ecr.aws/docker/library/python:3.12-alpine3.20

# Copy uv binary from official uv image
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /usr/local/bin/

# Install git and build-essential
RUN apk add --no-cache git build-base

# Set the working directory
WORKDIR /sourcecode

# Copy pyproject.toml and uv.lock
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv
RUN uv sync --dev --no-install-project --verbose

# Allow git operations in the mounted volume
RUN git config --global --add safe.directory /sourcecode
RUN git config --global user.email "pre-commit@local" && \
    git config --global user.name "pre-commit"

# Init a temporary git repo so pre-commit can operate on the project files
CMD sh -c "git init && git add -A && pre-commit run --all-files"
