FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY data_exports_agent/ data_exports_agent/
RUN pip install --no-cache-dir -r data_exports_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "data_exports_agent"]
