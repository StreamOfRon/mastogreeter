FROM python:3.11-alpine AS builder

COPY requirements.txt /
RUN python -m venv /venv && \
    source /venv/bin/activate && \
    pip install --require-virtualenv --no-compile --no-clean --no-cache-dir -r /requirements.txt

FROM python:3.11-alpine as service

ENV PATH="/venv/bin:$PATH"
COPY --from=builder /venv /
COPY main.py message.txt /app/

ENTRYPOINT ["python"]
CMD ["/app/main.py"]
