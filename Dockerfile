# Use an official Python runtime as a parent image
FROM python:3.8-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create directory for credentials
RUN mkdir -p credentials

# Make port 80 available to the world outside this container
# EXPOSE 80

# Run bot.py when the container launches
CMD ["python", "bot.py"]
