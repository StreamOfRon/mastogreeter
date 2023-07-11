FROM python:3.11-alpine AS builder

COPY requirements.txt /
RUN python -m venv /venv && \
    source /venv/bin/activate && \
    pip install --require-virtualenv --no-compile --no-clean --no-cache-dir -r /requirements.txt

FROM python:3.11-alpine as service
COPY --from=builder /venv /venv
COPY main.py message.txt /app/

ENV PATH="/venv/bin:$PATH"
ENV PYTHONPATH="/venv"
ENTRYPOINT ["python"]
CMD ["/app/main.py"]
