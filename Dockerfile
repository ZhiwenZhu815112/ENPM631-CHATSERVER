# Dockerfile for Chat Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY chat_server.py .
COPY user_thread.py .
COPY db_manager.py .
COPY redis_manager.py .

# Expose the chat server port
EXPOSE 8080

# Set environment variables for database connection
ENV DB_HOST=postgres
ENV DB_PORT=5432
ENV DB_NAME=chatdb
ENV DB_USER=chatuser
ENV DB_PASS=chatpass

# Run the chat server
CMD ["python", "chat_server.py", "8080"]
