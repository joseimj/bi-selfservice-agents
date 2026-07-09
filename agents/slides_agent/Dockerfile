FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY slides_agent/ slides_agent/
RUN pip install --no-cache-dir -r slides_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "slides_agent"]
