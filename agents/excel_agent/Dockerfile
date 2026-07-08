FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY excel_agent/ excel_agent/
RUN pip install --no-cache-dir -r excel_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "excel_agent"]
