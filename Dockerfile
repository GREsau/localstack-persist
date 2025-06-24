ARG LOCALSTACK_VERSION
FROM localstack/localstack:${LOCALSTACK_VERSION}

LABEL maintainer="Graham Esau (hello@graham.cool)"

VOLUME /persisted-data

COPY setup.cfg setup.py /localstack-persist/
COPY src /localstack-persist/src

RUN . .venv/bin/activate && pip3 install jsonpickle==4.1.1 watchdog==6.0.0 /localstack-persist && rm -rf /localstack-persist