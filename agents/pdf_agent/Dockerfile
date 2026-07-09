FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY pdf_agent/ pdf_agent/
RUN pip install --no-cache-dir -r pdf_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "pdf_agent"]
