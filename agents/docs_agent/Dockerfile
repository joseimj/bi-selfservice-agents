FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY docs_agent/ docs_agent/
RUN pip install --no-cache-dir -r docs_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "docs_agent"]
