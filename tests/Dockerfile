# Build context is an isolated test directory containing artifacts/*.whl.
ARG HA_VERSION=2025.12.0
FROM ghcr.io/home-assistant/home-assistant:${HA_VERSION}
RUN uv pip install --system --index https://pypi.org/simple pytest==8.4.2 pytest-asyncio==1.1.1 pip==25.3
COPY artifacts/*.whl /wheels/
ARG LIBRARY_WHEEL
# For legacy runtime tests only; candidate installation must use the default.
ARG LEGACY_METADATA_WORKAROUND=""
RUN python -m pip install --no-deps ${LEGACY_METADATA_WORKAROUND} /wheels/${LIBRARY_WHEEL}
WORKDIR /workspace
ENTRYPOINT []
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]
