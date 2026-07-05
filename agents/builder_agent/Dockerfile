FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY builder_agent/ builder_agent/
RUN pip install --no-cache-dir -r builder_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "builder_agent"]
