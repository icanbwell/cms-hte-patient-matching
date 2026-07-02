FROM public.ecr.aws/docker/library/python:3.12-alpine3.20

# Set terminal width (COLUMNS) and height (LINES)
ENV COLUMNS=300

# Install git, build-essential, and pipenv
RUN apk add --no-cache git build-base && \
    pip install pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile* ./

# Install dependencies using pipenv
RUN pipenv sync --dev --system

# Set the working directory
WORKDIR /sourcecode

# Allow git operations in the mounted volume
RUN git config --global --add safe.directory /sourcecode
RUN git config --global user.email "pre-commit@local" && \
    git config --global user.name "pre-commit"

# Init a temporary git repo so pre-commit can operate on the project files
CMD sh -c "git init && git add -A && pre-commit run --all-files"
