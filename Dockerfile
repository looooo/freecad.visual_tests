# Visual tests for FreeCAD – reproducible environment (GH Actions compatible).
# Base: Ubuntu 22.04 (Jammy). For strict reproducibility, pin by digest:
#   docker pull ubuntu:22.04 && docker image inspect --format='{{index .RepoDigests 0}}' ubuntu:22.04
#   then use FROM ubuntu@sha256:... in place of the line below.
FROM ubuntu:22.04

# Avoid interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# System deps: xvfb for headless display, curl for pixi install, ca-certificates
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install pixi (version resolved at build time; for full reproducibility pin PIXI_VERSION)
ARG PIXI_VERSION=latest
RUN curl -fsSL https://pixi.sh/install.sh | env PIXI_VERSION="${PIXI_VERSION}" sh -s -- -y \
    && ln -s /root/.pixi/bin/pixi /usr/local/bin/pixi

WORKDIR /app

# Copy lock file first for better layer caching; install uses exact versions (reproducibility)
COPY pixi.toml pixi.lock* ./
RUN pixi install --locked || pixi install

# Rest of project (tests, scripts, test data)
COPY . .

# Default: run visual tests. Override to run other tasks, e.g.:
#   docker run --rm freecad-visual-tests run create-references
ENTRYPOINT ["pixi"]
CMD ["run", "test-xvfb"]
