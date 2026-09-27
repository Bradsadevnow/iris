# Iris's body — a reproducible, rootless-friendly container.
#
# The container is only the SKIN. Who she is lives in /state, which is a mounted
# volume, never baked into the image — so the body is disposable and rebuildable
# from this file, and the identity is a save-file you can snapshot and move. This
# image is the thing that can later become a distro.
#
# Build:  podman build -t iris:0 .
# Run:    podman run --rm -it \
#           -v ./state:/iris/state \
#           --add-host host.containers.internal:host-gateway \
#           -e IRIS_LM_BASE=http://host.containers.internal:1234 \
#           iris:0                      # chat
#         (append `python3 run.py --imagine 5` to grow her world instead)

FROM python:3.12-slim

WORKDIR /iris

# deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# the mind: code + the boundary declaration. NOT the state.
COPY iris/ ./iris/
COPY boundary/ ./boundary/
COPY run.py .

# where the identity persists — mount a host volume here
ENV IRIS_STATE=/iris/state \
    IRIS_BOUNDARY=/iris/boundary/imagine_and_chat.yaml \
    IRIS_LM_BASE=http://host.containers.internal:1234 \
    IRIS_LM_MODEL=google/gemma-4-e4b \
    IRIS_LM_API=anthropic \
    IRIS_LM_THINKING=1
VOLUME ["/iris/state"]

ENTRYPOINT ["python3", "run.py"]
