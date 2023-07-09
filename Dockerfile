FROM python3.11-alpine AS builder

COPY requirements.txt /
RUN python -m venv /venv && \
    source /venv/bin/activate && \
    pip install --require-virtualenv --no-compile --no-clean --no-cache-dir /requirements.txt


FROM python3.11-alpine as service

ENV PATH="/venv/bin:$PATH"
COPY main.py template.txt /app/
ENTRYPOINT ["python"]
CMD ["/app/main.py"]
