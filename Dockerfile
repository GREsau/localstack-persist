FROM localstack/localstack:2.2.0

ENV PERSISTENCE=1

COPY setup.cfg setup.py /localstack-compere/
COPY src /localstack-compere/src

RUN . .venv/bin/activate && pip3 install jsonpickle /localstack-compere