FROM python:3.12-slim
WORKDIR /app
COPY common/ common/
COPY render_agent/ render_agent/
RUN pip install --no-cache-dir -r render_agent/requirements.txt
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "render_agent"]
