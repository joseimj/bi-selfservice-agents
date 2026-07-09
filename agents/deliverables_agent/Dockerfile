FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY deliverables_agent/ deliverables_agent/
RUN pip install --no-cache-dir -r deliverables_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "deliverables_agent"]
