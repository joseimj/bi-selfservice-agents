FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY catalog_agent/ catalog_agent/
RUN pip install --no-cache-dir -r catalog_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "catalog_agent"]
