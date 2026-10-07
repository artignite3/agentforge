FROM python:3.11-slim
RUN groupadd -g 10001 tool && useradd -u 10001 -g tool -M tool
COPY runner.py /runner.py
USER 10001:10001
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python", "-I", "/runner.py"]
