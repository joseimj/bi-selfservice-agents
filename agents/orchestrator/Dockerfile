FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY orchestrator/ orchestrator/
RUN pip install --no-cache-dir -r orchestrator/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "orchestrator"]
