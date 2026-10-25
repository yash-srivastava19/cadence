FROM python:3.12-slim
ARG CADENCE_REF=main
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && pip install --no-cache-dir "git+https://github.com/yash-srivastava19/cadence@${CADENCE_REF}" \
    && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
RUN useradd --create-home sandbox
USER sandbox
ENTRYPOINT ["cadence", "sandbox"]
