ARG BUILD_FROM=ghcr.io/home-assistant/amd64-addon-base:latest
FROM $BUILD_FROM

# Set environment variables
ENV LANG C.UTF-8

# Install Python and required packages
RUN apk add --no-cache python3 py3-pip

# Copy requirement file and install Python dependencies
WORKDIR /usr/src/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and run script
COPY app/ ./app/
COPY run.sh /run.sh

# Ensure run script is executable
RUN chmod a+x /run.sh

# Default command
CMD [ "/run.sh" ]
